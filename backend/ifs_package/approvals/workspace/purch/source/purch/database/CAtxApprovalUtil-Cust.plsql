-----------------------------------------------------------------------------
--
--  Logical unit: CAtxApprovalUtil
--  Component:    PURCH
--
--  IFS Developer Studio Template Version 3.0
--
--  AtroNexus: approve and reject purchase requisition lines from email.
--
--  How it works
--  1. The standard event PUR_REQ_LINE_TO_BE_AUTHORIZED (PurchReqLineApproval)
--     calls Notify_Pr_Line from an event action. It finds the approval
--     step(s) whose turn it is, the people allowed to act on them, signs one
--     token per person, and queues one JSON message to AtroNexus through
--     IFS Connect (routing rule C_ATX_APPROVAL_RULE).
--  2. AtroNexus emails each person a one-time link. When they decide,
--     AtroNexus calls CAtxApprovalHandling (Approve_Pr_Line / Reject_Pr_Line)
--     as its service user, passing the token back.
--  3. IFS checks the token, impersonates the person the token was issued
--     for, and runs the standard authorization or rejection. IFS applies
--     that person's authority, substitutes, superiors and limits, and
--     records them as the signer.
--
--  Security
--  - Tokens are HMAC-SHA256 over the step and the person, keyed with the
--    object property CAtxApproval / * / HMAC_SECRET, which only IFS knows.
--    AtroNexus never sees the secret, so it can only act on requests IFS
--    issued, for the person IFS named, and only within that person's rights.
--  - A token stops working once the step is signed (IFS's own data) and
--    after token_lifetime_days_.
--  - The service user needs the system privilege IMPERSONATE USER.
--
--  Date    Sign       History
--  ------  ---------  ---------------------------------------------------------
--  261114  AtroNexus  Created.
-----------------------------------------------------------------------------

layer Cust;

-------------------- PUBLIC DECLARATIONS ------------------------------------


-------------------- PRIVATE DECLARATIONS -----------------------------------

-- Where the admin stores the shared secret (Object Properties page).
secret_lu_            CONSTANT VARCHAR2(30)  := 'CAtxApproval';
secret_property_      CONSTANT VARCHAR2(30)  := 'HMAC_SECRET';
-- Message function the IFS Connect routing rule matches on.
message_function_     CONSTANT VARCHAR2(30)  := 'C_ATX_APPROVAL_REQUEST';
-- Version of the JSON contract with AtroNexus.
contract_version_     CONSTANT NUMBER        := 1;
-- A token older than this is refused even if the step is still open.
token_lifetime_days_  CONSTANT NUMBER        := 30;
min_secret_length_    CONSTANT NUMBER        := 32;
kind_pr_line_         CONSTANT VARCHAR2(10)  := 'PR_LINE';


-------------------- LU SPECIFIC IMPLEMENTATION METHODS ---------------------

FUNCTION Sha256___ (
   data_ IN RAW ) RETURN RAW
IS
   hash_ RAW(32);
BEGIN
   -- STANDARD_HASH needs no extra grants (unlike DBMS_CRYPTO).
   SELECT STANDARD_HASH(data_, 'SHA256') INTO hash_ FROM dual;
   RETURN hash_;
END Sha256___;


-- HMAC-SHA256 (RFC 2104), returned as lowercase hex.
FUNCTION Hmac_Sha256___ (
   key_     IN VARCHAR2,
   message_ IN VARCHAR2 ) RETURN VARCHAR2
IS
   block_size_ CONSTANT PLS_INTEGER := 64;
   key_raw_    RAW(2000) := UTL_I18N.STRING_TO_RAW(key_, 'AL32UTF8');
   ipad_       RAW(64);
   opad_       RAW(64);
BEGIN
   IF UTL_RAW.LENGTH(key_raw_) > block_size_ THEN
      key_raw_ := Sha256___(key_raw_);
   END IF;
   IF UTL_RAW.LENGTH(key_raw_) < block_size_ THEN
      key_raw_ := UTL_RAW.CONCAT(key_raw_, UTL_RAW.COPIES('00', block_size_ - UTL_RAW.LENGTH(key_raw_)));
   END IF;
   ipad_ := UTL_RAW.BIT_XOR(key_raw_, UTL_RAW.COPIES('36', block_size_));
   opad_ := UTL_RAW.BIT_XOR(key_raw_, UTL_RAW.COPIES('5C', block_size_));
   RETURN LOWER(RAWTOHEX(
      Sha256___(UTL_RAW.CONCAT(opad_,
         Sha256___(UTL_RAW.CONCAT(ipad_, UTL_I18N.STRING_TO_RAW(message_, 'AL32UTF8')))))));
END Hmac_Sha256___;


FUNCTION Get_Secret___ RETURN VARCHAR2
IS
   secret_ VARCHAR2(2000);
BEGIN
   secret_ := Object_Property_API.Get_Value(secret_lu_, '*', secret_property_);
   IF secret_ IS NULL OR LENGTH(secret_) < min_secret_length_ THEN
      Error_SYS.Appl_General(lu_name_, 'ATXNOSECRET: AtroNexus approvals are not set up: add the object property :P1 / * / :P2 with a random value of at least :P3 characters.',
                             secret_lu_, secret_property_, min_secret_length_);
   END IF;
   RETURN secret_;
END Get_Secret___;


-- The signed text. Changing it invalidates every outstanding token.
FUNCTION Token_Message___ (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2,
   sequence_no_    IN NUMBER,
   fnd_user_       IN VARCHAR2,
   issued_at_      IN NUMBER ) RETURN VARCHAR2
IS
BEGIN
   RETURN kind_pr_line_ || '|' || requisition_no_ || '|' || line_no_ || '|' || release_no_ || '|' ||
          TO_CHAR(sequence_no_) || '|' || UPPER(fnd_user_) || '|' || TO_CHAR(issued_at_);
END Token_Message___;


FUNCTION Make_Token___ (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2,
   sequence_no_    IN NUMBER,
   fnd_user_       IN VARCHAR2,
   issued_at_      IN NUMBER ) RETURN VARCHAR2
IS
BEGIN
   RETURN Hmac_Sha256___(Get_Secret___,
                         Token_Message___(requisition_no_, line_no_, release_no_, sequence_no_, fnd_user_, issued_at_));
END Make_Token___;


-- Seconds since 1970-01-01 UTC.
FUNCTION Epoch_Now___ RETURN NUMBER
IS
BEGIN
   RETURN ROUND((CAST(SYS_EXTRACT_UTC(SYSTIMESTAMP) AS DATE) - DATE '1970-01-01') * 86400);
END Epoch_Now___;


-- Raises unless the token is the one IFS issued for this step and person,
-- and isn't too old. Compares in constant time.
PROCEDURE Check_Token___ (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2,
   sequence_no_    IN NUMBER,
   fnd_user_       IN VARCHAR2,
   issued_at_      IN NUMBER,
   token_          IN VARCHAR2 )
IS
   expected_ VARCHAR2(64);
   diff_     PLS_INTEGER := 0;
BEGIN
   IF token_ IS NULL OR issued_at_ IS NULL OR fnd_user_ IS NULL THEN
      Error_SYS.Appl_General(lu_name_, 'ATXBADTOKEN: This approval link is not valid.');
   END IF;
   IF issued_at_ < Epoch_Now___ - token_lifetime_days_ * 86400 OR issued_at_ > Epoch_Now___ + 300 THEN
      Error_SYS.Appl_General(lu_name_, 'ATXOLDTOKEN: This approval link has expired. Authorize in IFS instead.');
   END IF;
   expected_ := Make_Token___(requisition_no_, line_no_, release_no_, sequence_no_, fnd_user_, issued_at_);
   IF LENGTH(token_) != LENGTH(expected_) THEN
      Error_SYS.Appl_General(lu_name_, 'ATXBADTOKEN: This approval link is not valid.');
   END IF;
   FOR i_ IN 1 .. LENGTH(expected_) LOOP
      IF SUBSTR(token_, i_, 1) != SUBSTR(expected_, i_, 1) THEN
         diff_ := diff_ + 1;
      END IF;
   END LOOP;
   IF diff_ != 0 THEN
      Error_SYS.Appl_General(lu_name_, 'ATXBADTOKEN: This approval link is not valid.');
   END IF;
END Check_Token___;


-- The approval step row, or an error if it doesn't exist.
FUNCTION Get_Step___ (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2,
   sequence_no_    IN NUMBER ) RETURN purch_req_line_approval_tab%ROWTYPE
IS
   step_ purch_req_line_approval_tab%ROWTYPE;
   CURSOR get_step IS
      SELECT *
      FROM   purch_req_line_approval_tab
      WHERE  requisition_no = requisition_no_
      AND    line_no        = line_no_
      AND    release_no     = release_no_
      AND    sequence_no    = sequence_no_;
BEGIN
   OPEN get_step;
   FETCH get_step INTO step_;
   IF get_step%NOTFOUND THEN
      CLOSE get_step;
      Error_SYS.Appl_General(lu_name_, 'ATXNOSTEP: This authorization step no longer exists.');
   END IF;
   CLOSE get_step;
   RETURN step_;
END Get_Step___;


-- PENDING, SIGNED, NOT_YET (an earlier step is still open) or REJECTED.
FUNCTION Step_Status___ (
   step_ IN purch_req_line_approval_tab%ROWTYPE ) RETURN VARCHAR2
IS
BEGIN
   IF Purchase_Req_Line_API.Get_Authorization_Rejected_Db(step_.requisition_no, step_.line_no, step_.release_no) = 'TRUE' THEN
      RETURN 'REJECTED';
   ELSIF step_.signature_id IS NOT NULL THEN
      RETURN 'SIGNED';
   ELSIF NOT Pur_Req_Line_Approval_Util_API.Ok_To_Approve(step_.requisition_no, step_.line_no, step_.release_no, step_.route) THEN
      RETURN 'NOT_YET';
   END IF;
   RETURN 'PENDING';
END Step_Status___;


PROCEDURE Add_Approver___ (
   approvers_    IN OUT JSON_ARRAY_T,
   seen_         IN OUT VARCHAR2,
   company_      IN     VARCHAR2,
   authorize_id_ IN     VARCHAR2,
   fnd_user_     IN     VARCHAR2,
   step_         IN     purch_req_line_approval_tab%ROWTYPE,
   issued_at_    IN     NUMBER )
IS
   email_    VARCHAR2(200);
   approver_ JSON_OBJECT_T;
BEGIN
   IF fnd_user_ IS NULL OR INSTR(seen_, '^' || fnd_user_ || '^') > 0 THEN
      RETURN;
   END IF;
   email_ := Fnd_User_API.Get_Property(fnd_user_, 'SMTP_MAIL_ADDRESS');
   IF email_ IS NULL THEN
      RETURN;  -- nobody to email; they can still authorize in IFS
   END IF;
   seen_ := seen_ || fnd_user_ || '^';
   approver_ := JSON_OBJECT_T();
   approver_.PUT('fndUser', fnd_user_);
   approver_.PUT('authorizeId', authorize_id_);
   approver_.PUT('name', NVL(Fnd_User_API.Get_Description(fnd_user_), fnd_user_));
   approver_.PUT('email', email_);
   approver_.PUT('token', Make_Token___(step_.requisition_no, step_.line_no, step_.release_no,
                                        step_.sequence_no, fnd_user_, issued_at_));
   approvers_.APPEND(approver_);
END Add_Approver___;


-- An authorizer and their substitute, who IFS also lets act.
PROCEDURE Add_Authorizer___ (
   approvers_    IN OUT JSON_ARRAY_T,
   seen_         IN OUT VARCHAR2,
   company_      IN     VARCHAR2,
   authorize_id_ IN     VARCHAR2,
   step_         IN     purch_req_line_approval_tab%ROWTYPE,
   issued_at_    IN     NUMBER )
IS
   substitute_id_ VARCHAR2(20);
BEGIN
   IF authorize_id_ IS NULL THEN
      RETURN;
   END IF;
   Add_Approver___(approvers_, seen_, company_, authorize_id_,
                   Purchase_Authorizer_API.Get_Userid(company_, authorize_id_), step_, issued_at_);
   substitute_id_ := Pur_Auth_Substitute_API.Get_Auth_Substitute(company_, authorize_id_);
   IF substitute_id_ IS NOT NULL THEN
      Add_Approver___(approvers_, seen_, company_, substitute_id_,
                      Purchase_Authorizer_API.Get_Userid(company_, substitute_id_), step_, issued_at_);
   END IF;
END Add_Authorizer___;


-- Everyone who may act on the step. Version 1 covers authorizers, buyers,
-- requisitioners and authorization groups; position- and project-role-based
-- steps are skipped (those people authorize in IFS as usual).
FUNCTION Approvers___ (
   step_      IN purch_req_line_approval_tab%ROWTYPE,
   issued_at_ IN NUMBER ) RETURN JSON_ARRAY_T
IS
   approvers_ JSON_ARRAY_T := JSON_ARRAY_T();
   seen_      VARCHAR2(32000) := '^';
   CURSOR get_group_members IS
      SELECT pag.authorize_id
      FROM   purch_authorize_group_line_tab pag
      WHERE  pag.company            = step_.company
      AND    pag.authorize_group_id = step_.authorize_group_id;
BEGIN
   IF step_.authorize_id IS NOT NULL THEN
      Add_Authorizer___(approvers_, seen_, step_.company, step_.authorize_id, step_, issued_at_);
   ELSIF step_.buyer_code IS NOT NULL THEN
      Add_Authorizer___(approvers_, seen_, step_.company, step_.buyer_code, step_, issued_at_);
   ELSIF step_.requisitioner_code IS NOT NULL THEN
      Add_Authorizer___(approvers_, seen_, step_.company, step_.requisitioner_code, step_, issued_at_);
   ELSIF step_.authorize_group_id IS NOT NULL THEN
      FOR member_ IN get_group_members LOOP
         Add_Authorizer___(approvers_, seen_, step_.company, member_.authorize_id, step_, issued_at_);
      END LOOP;
   END IF;
   RETURN approvers_;
END Approvers___;


-- What the approver sees: read live, so the page always shows the current line.
FUNCTION Line_Summary___ (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2 ) RETURN JSON_OBJECT_T
IS
   summary_    JSON_OBJECT_T := JSON_OBJECT_T();
   line_total_ NUMBER;
   CURSOR get_line IS
      SELECT part_no, description, original_qty, unit_meas, buy_unit_meas, buy_unit_price,
             currency_code, wanted_receipt_date, vendor_no, contract, requisitioner_code,
             buyer_code, note_text
      FROM   purchase_req_line_all
      WHERE  requisition_no = requisition_no_
      AND    line_no        = line_no_
      AND    release_no     = release_no_;
   line_ get_line%ROWTYPE;
BEGIN
   OPEN get_line;
   FETCH get_line INTO line_;
   CLOSE get_line;
   IF line_.part_no IS NOT NULL THEN
      line_total_ := Purchase_Req_Line_Part_API.Get_Line_Total(requisition_no_, line_no_, release_no_);
   ELSE
      line_total_ := Purchase_Req_Line_Nopart_API.Get_Line_Total(requisition_no_, line_no_, release_no_);
   END IF;
   summary_.PUT('partNo', line_.part_no);
   summary_.PUT('description', line_.description);
   summary_.PUT('quantity', line_.original_qty);
   summary_.PUT('unit', NVL(line_.buy_unit_meas, line_.unit_meas));
   summary_.PUT('unitPrice', line_.buy_unit_price);
   summary_.PUT('currency', line_.currency_code);
   summary_.PUT('lineTotal', line_total_);
   summary_.PUT('wantedReceiptDate', TO_CHAR(line_.wanted_receipt_date, 'YYYY-MM-DD'));
   summary_.PUT('site', line_.contract);
   summary_.PUT('supplierId', line_.vendor_no);
   summary_.PUT('supplierName', CASE WHEN line_.vendor_no IS NOT NULL THEN Supplier_API.Get_Vendor_Name(line_.vendor_no) END);
   summary_.PUT('requisitioner', line_.requisitioner_code);
   summary_.PUT('buyer', line_.buyer_code);
   summary_.PUT('note', SUBSTR(line_.note_text, 1, 1000));
   RETURN summary_;
END Line_Summary___;


-------------------- LU SPECIFIC PRIVATE METHODS ----------------------------


-------------------- LU SPECIFIC PROTECTED METHODS --------------------------


-------------------- LU SPECIFIC PUBLIC METHODS -----------------------------


-------------------- LU CUST NEW METHODS -------------------------------------

-- Called from the event action on PUR_REQ_LINE_TO_BE_AUTHORIZED. Queues one
-- message to AtroNexus per approval step whose turn it is. Never raises: a
-- problem here must not stop the requisition from being released.
PROCEDURE Notify_Pr_Line (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2 )
IS
   issued_at_  NUMBER := Epoch_Now___;
   message_    JSON_OBJECT_T;
   approvers_  JSON_ARRAY_T;
   json_       CLOB;
   CURSOR get_current_steps IS
      SELECT *
      FROM   purch_req_line_approval_tab s
      WHERE  s.requisition_no = requisition_no_
      AND    s.line_no        = line_no_
      AND    s.release_no     = release_no_
      AND    s.signature_id   IS NULL
      AND    s.route = (SELECT MIN(route)
                        FROM   purch_req_line_approval_tab
                        WHERE  requisition_no = requisition_no_
                        AND    line_no        = line_no_
                        AND    release_no     = release_no_
                        AND    signature_id   IS NULL);
BEGIN
   FOR step_ IN get_current_steps LOOP
      approvers_ := Approvers___(step_, issued_at_);
      IF approvers_.GET_SIZE > 0 THEN
         message_ := JSON_OBJECT_T();
         message_.PUT('version', contract_version_);
         message_.PUT('kind', kind_pr_line_);
         message_.PUT('company', step_.company);
         message_.PUT('requisitionNo', step_.requisition_no);
         message_.PUT('lineNo', step_.line_no);
         message_.PUT('releaseNo', step_.release_no);
         message_.PUT('sequenceNo', step_.sequence_no);
         message_.PUT('route', step_.route);
         message_.PUT('issuedAt', issued_at_);
         message_.PUT('approvers', approvers_);
         message_.PUT('summary', Line_Summary___(step_.requisition_no, step_.line_no, step_.release_no));
         json_ := message_.TO_CLOB;
         Plsqlap_Server_API.Post_Outbound_Message(json_             => json_,
                                                  message_type_     => 'EVENT',
                                                  message_function_ => message_function_,
                                                  subject_          => 'AtroNexus approval ' || step_.requisition_no || '-' ||
                                                                       step_.line_no || '-' || step_.release_no,
                                                  is_json_          => TRUE);
      END IF;
   END LOOP;
EXCEPTION
   WHEN OTHERS THEN
      Log_SYS.Fnd_Trace_(Log_SYS.error_, 'C_Atx_Approval_Util_API.Notify_Pr_Line failed for ' ||
                         requisition_no_ || '-' || line_no_ || '-' || release_no_ || ': ' || SQLERRM);
END Notify_Pr_Line;


-- Live status and summary for the approval page. Raises if the token is invalid.
FUNCTION Get_Pr_Line_Status (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2,
   sequence_no_    IN NUMBER,
   fnd_user_       IN VARCHAR2,
   issued_at_      IN NUMBER,
   token_          IN VARCHAR2 ) RETURN CLOB
IS
   step_   purch_req_line_approval_tab%ROWTYPE;
   result_ JSON_OBJECT_T := JSON_OBJECT_T();
BEGIN
   Check_Token___(requisition_no_, line_no_, release_no_, sequence_no_, fnd_user_, issued_at_, token_);
   step_ := Get_Step___(requisition_no_, line_no_, release_no_, sequence_no_);
   result_.PUT('status', Step_Status___(step_));
   result_.PUT('company', step_.company);
   result_.PUT('signedBy', step_.signature_id);
   result_.PUT('summary', Line_Summary___(requisition_no_, line_no_, release_no_));
   RETURN result_.TO_CLOB;
END Get_Pr_Line_Status;


-- The company's reasons for rejecting an authorization step.
FUNCTION Get_Reject_Reasons (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2,
   sequence_no_    IN NUMBER,
   fnd_user_       IN VARCHAR2,
   issued_at_      IN NUMBER,
   token_          IN VARCHAR2 ) RETURN CLOB
IS
   step_    purch_req_line_approval_tab%ROWTYPE;
   reasons_ JSON_ARRAY_T := JSON_ARRAY_T();
   reason_  JSON_OBJECT_T;
   CURSOR get_reasons (company_ VARCHAR2) IS
      SELECT reject_reason_id, description
      FROM   pur_auth_reject_reason_tab
      WHERE  company = company_
      ORDER BY reject_reason_id;
BEGIN
   Check_Token___(requisition_no_, line_no_, release_no_, sequence_no_, fnd_user_, issued_at_, token_);
   step_ := Get_Step___(requisition_no_, line_no_, release_no_, sequence_no_);
   FOR rec_ IN get_reasons(step_.company) LOOP
      reason_ := JSON_OBJECT_T();
      reason_.PUT('id', rec_.reject_reason_id);
      reason_.PUT('description', rec_.description);
      reasons_.APPEND(reason_);
   END LOOP;
   RETURN reasons_.TO_CLOB;
END Get_Reject_Reasons;


-- Authorizes the step as the person the token was issued for.
FUNCTION Approve_Pr_Line (
   requisition_no_ IN VARCHAR2,
   line_no_        IN VARCHAR2,
   release_no_     IN VARCHAR2,
   sequence_no_    IN NUMBER,
   fnd_user_       IN VARCHAR2,
   issued_at_      IN NUMBER,
   token_          IN VARCHAR2 ) RETURN VARCHAR2
IS
   step_              purch_req_line_approval_tab%ROWTYPE;
   status_            VARCHAR2(20);
   current_user_name_ VARCHAR2(30);
   info_              VARCHAR2(32000);
BEGIN
   Check_Token___(requisition_no_, line_no_, release_no_, sequence_no_, fnd_user_, issued_at_, token_);
   step_   := Get_Step___(requisition_no_, line_no_, release_no_, sequence_no_);
   status_ := Step_Status___(step_);
   IF status_ != 'PENDING' THEN
      RETURN status_;
   END IF;

   Fnd_Session_Util_API.Impersonate_Fnd_User_(UPPER(fnd_user_));
   BEGIN
      -- The same checks and call as the IFS Authorize command.
      Purch_Req_Line_Approval_API.Check_Authorizer(current_user_name_,
                                                   step_.company,
                                                   step_.authorize_id,
                                                   step_.authorize_group_id,
                                                   step_.requisitioner_code,
                                                   step_.pos_code,
                                                   step_.org_code,
                                                   step_.project_role_id,
                                                   requisition_no_,
                                                   line_no_,
                                                   release_no_,
                                                   sequence_no_,
                                                   step_.buyer_code);
      Purch_Req_Line_Approval_API.Authorize__(info_, requisition_no_, line_no_, release_no_, sequence_no_, current_user_name_);
      Fnd_Session_Util_API.Reset_Fnd_User_;
   EXCEPTION
      WHEN OTHERS THEN
         Fnd_Session_Util_API.Reset_Fnd_User_;
         RAISE;
   END;
   RETURN 'APPROVED';
END Approve_Pr_Line;


-- Rejects the step as the person the token was issued for.
FUNCTION Reject_Pr_Line (
   requisition_no_   IN VARCHAR2,
   line_no_          IN VARCHAR2,
   release_no_       IN VARCHAR2,
   sequence_no_      IN NUMBER,
   fnd_user_         IN VARCHAR2,
   issued_at_        IN NUMBER,
   token_            IN VARCHAR2,
   reject_reason_id_ IN VARCHAR2,
   reject_note_      IN VARCHAR2 ) RETURN VARCHAR2
IS
   step_   purch_req_line_approval_tab%ROWTYPE;
   status_ VARCHAR2(20);
   info_   VARCHAR2(32000);
BEGIN
   Check_Token___(requisition_no_, line_no_, release_no_, sequence_no_, fnd_user_, issued_at_, token_);
   step_   := Get_Step___(requisition_no_, line_no_, release_no_, sequence_no_);
   status_ := Step_Status___(step_);
   IF status_ != 'PENDING' THEN
      RETURN status_;
   END IF;

   Fnd_Session_Util_API.Impersonate_Fnd_User_(UPPER(fnd_user_));
   BEGIN
      -- Checks the authorizer, the reason and active RFQs, then rejects.
      Pur_Req_Line_Approval_Util_API.Update_Rejection_Details__(info_, requisition_no_, line_no_, release_no_,
                                                               sequence_no_, step_.company,
                                                               reject_reason_id_, SUBSTR(reject_note_, 1, 2000));
      Fnd_Session_Util_API.Reset_Fnd_User_;
   EXCEPTION
      WHEN OTHERS THEN
         Fnd_Session_Util_API.Reset_Fnd_User_;
         RAISE;
   END;
   RETURN 'REJECTED';
END Reject_Pr_Line;
