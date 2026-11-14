-----------------------------------------------------------------------------
--
--  Logical unit: CAtxMessageUtil
--  Component:    FNDBAS
--
--  IFS Developer Studio Template Version 3.0
--
--  AtroNexus messaging hub: send a WhatsApp message from anywhere in IFS.
--
--  Call Send from an event action (Execute Online SQL), a workflow or your
--  own PL/SQL, with a scenario code set up in AtroNexus and the values its
--  template needs. Build the values with Params, which escapes them:
--
--     C_Atx_Message_Util_API.Send('ORDER_SHIPPED',
--        C_Atx_Message_Util_API.Params('phone',        '&PHONE',
--                                      'customerName', '&CUSTOMER_NAME',
--                                      'orderNo',      '&ORDER_NO'));
--
--  The message is queued to AtroNexus through IFS Connect (routing rule
--  C_ATX_MESSAGE_RULE), so it leaves after the transaction commits, and a
--  message AtroNexus couldn't send stays in Application Messages with the
--  reason and can be resent. Each message carries a unique messageId, so a
--  resend never sends it twice.
--
--  Send never raises: a problem here must not stop the user's own work. It
--  writes to the trace instead. Use Send_Or_Fail when you want an error.
--
--  Date    Sign       History
--  ------  ---------  ---------------------------------------------------------
--  261114  AtroNexus  Created.
-----------------------------------------------------------------------------

layer Cust;

-------------------- PUBLIC DECLARATIONS ------------------------------------


-------------------- PRIVATE DECLARATIONS -----------------------------------

-- Message function the IFS Connect routing rule matches on.
message_function_  CONSTANT VARCHAR2(30) := 'C_ATX_MESSAGE';
-- Version of the JSON contract with AtroNexus.
contract_version_  CONSTANT NUMBER       := 1;


-------------------- LU SPECIFIC IMPLEMENTATION METHODS ---------------------

PROCEDURE Add_Param___ (
   params_ IN OUT NOCOPY JSON_OBJECT_T,
   name_   IN VARCHAR2,
   value_  IN VARCHAR2 )
IS
BEGIN
   IF name_ IS NOT NULL THEN
      params_.PUT(name_, value_);
   END IF;
END Add_Param___;


-------------------- LU SPECIFIC PUBLIC METHODS -----------------------------

-- Up to ten name/value pairs as a JSON object, e.g. {"phone":"0771234567"}.
-- Names are the {fields} used in the AtroNexus scenario.
FUNCTION Params (
   name1_  IN VARCHAR2 DEFAULT NULL, value1_  IN VARCHAR2 DEFAULT NULL,
   name2_  IN VARCHAR2 DEFAULT NULL, value2_  IN VARCHAR2 DEFAULT NULL,
   name3_  IN VARCHAR2 DEFAULT NULL, value3_  IN VARCHAR2 DEFAULT NULL,
   name4_  IN VARCHAR2 DEFAULT NULL, value4_  IN VARCHAR2 DEFAULT NULL,
   name5_  IN VARCHAR2 DEFAULT NULL, value5_  IN VARCHAR2 DEFAULT NULL,
   name6_  IN VARCHAR2 DEFAULT NULL, value6_  IN VARCHAR2 DEFAULT NULL,
   name7_  IN VARCHAR2 DEFAULT NULL, value7_  IN VARCHAR2 DEFAULT NULL,
   name8_  IN VARCHAR2 DEFAULT NULL, value8_  IN VARCHAR2 DEFAULT NULL,
   name9_  IN VARCHAR2 DEFAULT NULL, value9_  IN VARCHAR2 DEFAULT NULL,
   name10_ IN VARCHAR2 DEFAULT NULL, value10_ IN VARCHAR2 DEFAULT NULL ) RETURN CLOB
IS
   params_ JSON_OBJECT_T := JSON_OBJECT_T();
BEGIN
   Add_Param___(params_, name1_, value1_);
   Add_Param___(params_, name2_, value2_);
   Add_Param___(params_, name3_, value3_);
   Add_Param___(params_, name4_, value4_);
   Add_Param___(params_, name5_, value5_);
   Add_Param___(params_, name6_, value6_);
   Add_Param___(params_, name7_, value7_);
   Add_Param___(params_, name8_, value8_);
   Add_Param___(params_, name9_, value9_);
   Add_Param___(params_, name10_, value10_);
   RETURN params_.TO_CLOB;
END Params;


-- Queues one message to AtroNexus; raises if it can't (bad JSON, no routing).
PROCEDURE Send_Or_Fail (
   scenario_ IN VARCHAR2,
   params_   IN CLOB DEFAULT NULL )
IS
   message_ JSON_OBJECT_T := JSON_OBJECT_T();
   json_    CLOB;
BEGIN
   IF scenario_ IS NULL THEN
      Error_SYS.Appl_General(lu_name_, 'NOSCENARIO: Give the AtroNexus scenario code.');
   END IF;
   message_.PUT('version', contract_version_);
   message_.PUT('scenario', UPPER(scenario_));
   message_.PUT('params', JSON_OBJECT_T.PARSE(NVL(params_, TO_CLOB('{}'))));
   message_.PUT('messageId', LOWER(RAWTOHEX(SYS_GUID())));
   json_ := message_.TO_CLOB;
   Plsqlap_Server_API.Post_Outbound_Message(json_             => json_,
                                            message_type_     => 'EVENT',
                                            message_function_ => message_function_,
                                            subject_          => 'AtroNexus message ' || UPPER(scenario_),
                                            is_json_          => TRUE);
END Send_Or_Fail;


-- Queues one message to AtroNexus. Never raises; problems go to the trace.
PROCEDURE Send (
   scenario_ IN VARCHAR2,
   params_   IN CLOB DEFAULT NULL )
IS
BEGIN
   Send_Or_Fail(scenario_, params_);
EXCEPTION
   WHEN OTHERS THEN
      Log_SYS.Fnd_Trace_(Log_SYS.error_, 'C_Atx_Message_Util_API.Send failed for ' || scenario_ || ': ' || SQLERRM);
END Send;
