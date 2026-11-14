# AtroNexus approvals: IFS package

Lets IFS approvers approve or reject from an email, without signing in to IFS. IFS still records the real approver, with their own authority and limits.

Built and read against IFS Cloud 25.1 core. The package is organized by **approval type**; each organization picks the types it uses on the AtroNexus Approvals page, and the download contains the event actions for those types only. Built so far: **purchase requisition lines** (`PR_LINE`). Purchase orders, change orders, supplier invoices, expense sheets and document revisions are listed in AtroNexus as coming soon.

## What's in the package

| File | What it does |
| --- | --- |
| `workspace/purch/.../CAtxApprovalUtil-Cust.utility` / `.plsql` | Finds the approval step whose turn it is and its approvers, signs a token per approver, queues the message to AtroNexus, and approves or rejects as the real user |
| `workspace/purch/.../CAtxApprovalHandling-Cust.projection` / `.plsvc` | The API AtroNexus calls: `GetPrLineStatus`, `GetRejectReasons`, `ApprovePrLine`, `RejectPrLine` |
| `flows/<type>/` | The event action(s) of each approval type (`flows/pr_line/`: the standard event `PUR_REQ_LINE_TO_BE_AUTHORIZED`). The AtroNexus download puts the chosen types into one application configuration package, `config/C_ATX_APPROVALS.zip` |
| `config/connect/` | IFS Connect routing rule and routing address that POST the message to AtroNexus |

Component `PURCH`, layer `Cust`. No new tables. The utility and projection are shared by every type: a type adds its own functions and actions to them, and its event action(s) under `flows/`. The code for every built type is always deployed; the event actions decide which types IFS sends.

## How it works

1. A requisition line reaches an authorization step. IFS fires `PUR_REQ_LINE_TO_BE_AUTHORIZED`; the event action calls `C_Atx_Approval_Util_API.Notify_Pr_Line`.
2. The utility finds the step(s) whose turn it is (lowest unsigned route), and the people who may act: the authorizer and their substitute, or the buyer, the requisitioner, or the members of the authorization group. Each gets a token: HMAC-SHA256 over the step and the person, keyed with a secret only IFS knows.
3. One JSON message per step goes to AtroNexus through IFS Connect (`C_ATX_APPROVAL_RULE` → `C_ATX_APPROVAL_ADDR`). If AtroNexus is unreachable, the message waits in Application Messages and can be resent.
4. AtroNexus emails each person a one-time link. The page shows the line, read live from IFS.
5. On Approve or Reject, AtroNexus calls `CAtxApprovalHandling` as its service user and passes the token back. IFS checks the token, impersonates that person, runs the **standard** checks (`Check_Authorizer`, authorization limits, reject reasons, active RFQs) and the standard authorize or reject, then switches back. IFS records the person as the signer.

Problems in step 2 or 3 never block the requisition: they're written to the trace and the line can be authorized in IFS as usual.

## Security

- **AtroNexus never knows the secret.** It only passes back tokens IFS issued, so it can act only on steps IFS asked about, for the person IFS named, within that person's rights. Stolen service-user credentials alone can't approve anything.
- **A token works until the step is signed** (IFS's own data), and never longer than 30 days.
- **The service user needs `IMPERSONATE USER`.** Use a dedicated user for AtroNexus and grant it only this projection.
- **Security checkpoint `PURCH_REQ_AUTHORIZATION` must be off** (it is by default). If it's on, approvers are meant to re-enter their password, which email approval would bypass.

## Installation

1. **Build and deploy the code** (`workspace/purch`) like any customization: put the four files in the customer's `purch` component (`Cust` layer), build, and deploy.
2. **Set the secret.** *Application Base Setup → System Definitions → Object Properties*: add object `CAtxApproval`, key `*`, property `HMAC_SECRET`, with a random value of at least 32 characters. Keep it in IFS only; AtroNexus doesn't need it. Changing it invalidates links that haven't been used yet.
3. **Import the event action.** Import `config/C_ATX_APPROVALS.zip` under *Solution Manager → Configuration → Application Configuration Packages*. (Only the download from AtroNexus has it: it's built from `flows/` for the types you switched on. Switch on a type later? Download again and import the new zip.) Then, for purchase requisition lines, make sure the event `PUR_REQ_LINE_TO_BE_AUTHORIZED` (LU `PurchReqLineApproval`) is **enabled** under *Solution Manager → Events*.
   - Or create the action by hand on that event: type *Execute Online SQL*, with
     ```sql
     BEGIN
        C_Atx_Approval_Util_API.Notify_Pr_Line('&REQUISITION_NO', '&LINE_NO', '&RELEASE_NO');
     END;
     ```
4. **Import the routing address and rule** (`config/connect`) under *Solution Manager → Integration → IFS Connect*. In the download from AtroNexus the address already points at your AtroNexus. Open `C_ATX_APPROVAL_ADDR` and paste the **hook key** from AtroNexus (*Approvals → step 2*) into the bearer token field.
5. **Service user.** In AtroNexus, the IFS connection for approvals must sign in as a user that has a permission set granting the projection `CAtxApprovalHandling` and the system privilege `IMPERSONATE USER`.
6. **Test.** In AtroNexus, *Approvals → Setup → Check IFS*. Then release a test requisition line that needs authorization: the approver should get an email within a minute or two.

## Message to AtroNexus (version 1)

`kind` is the approval type. The record's keys are fields named by the type (for `PR_LINE`: `requisitionNo`, `lineNo`, `releaseNo`); everything else is the same for every type.

`POST https://atronexus.atrum0x.com/api/hooks/ifs/approvals` with `Authorization: Bearer <hook key>`:

```json
{
  "version": 1,
  "kind": "PR_LINE",
  "company": "10",
  "requisitionNo": "R1001", "lineNo": "1", "releaseNo": "1",
  "sequenceNo": 2, "route": 1,
  "issuedAt": 1794600000,
  "approvers": [
    { "fndUser": "JOHN", "authorizeId": "JOHN", "name": "John Perera", "email": "john@example.com", "token": "64 hex characters" }
  ],
  "summary": {
    "partNo": "P-100", "description": "Laptop", "quantity": 2, "unit": "pcs",
    "unitPrice": 250000, "currency": "LKR", "lineTotal": 500000,
    "wantedReceiptDate": "2026-12-01", "site": "MAIN",
    "supplierId": "S01", "supplierName": "Acme", "requisitioner": "MARY", "buyer": "BOB", "note": null
  }
}
```

## Limits of version 1

- Purchase requisition lines only. Purchase orders and change orders work the same way (standard events `PUR_ORD_LINE_TO_BE_AUTHORIZED`, `POCO_TO_BE_AUTHORIZED`) and come next.
- AtroNexus refuses (409) a message for a type that's switched off there, so IFS keeps it in Application Messages.
- Steps assigned to a **position** or **project role** aren't emailed; those people authorize in IFS as usual.
- People without an email address on their IFS user aren't emailed.
