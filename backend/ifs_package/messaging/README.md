# AtroNexus messaging hub: IFS package

Lets anything in IFS send a WhatsApp message: an event action, a workflow, or your own PL/SQL. You decide what is sent in AtroNexus, with **templates** (the text WhatsApp approves) and **scenarios** (a code IFS calls, which template it uses, who gets it, and which IFS values fill the template's variables).

Built against IFS Cloud 25.1. The PL/SQL hasn't been compiled on a real IFS yet.

## What's in the package

| File | What it does |
| --- | --- |
| `workspace/fndbas/.../CAtxMessageUtil-Cust.utility` / `.plsql` | `C_Atx_Message_Util_API.Send(scenario, params)` and `Params(...)` |
| `config/connect/` | IFS Connect routing rule and routing address that POST the message to AtroNexus |

Component `FNDBAS`, layer `Cust`, no tables, no projection. It can live in any component you customize; change the component in the two files.

## How it works

1. IFS calls `C_Atx_Message_Util_API.Send('ORDER_SHIPPED', params)`.
2. The utility queues a JSON message (`C_ATX_MESSAGE`) through IFS Connect. It leaves when the transaction commits; a rollback sends nothing.
3. The routing rule `C_ATX_MESSAGE_RULE` posts it to AtroNexus (`C_ATX_MESSAGE_ADDR`, Bearer hook key).
4. AtroNexus finds the scenario, fills the template with the values, and sends it through WhatsApp. It answers:
   - **200** sent;
   - **502** WhatsApp refused it (the reason is in the answer);
   - **409 / 422** the scenario or template isn't ready, or a value is missing.

   Anything other than 200 leaves the message in *Application Messages* with the reason, so it can be fixed and resent. Every message has a unique `messageId`, so a resend never sends it twice.

## Installation

1. **Build and deploy the code** (`workspace/fndbas`) like any customization.
2. **Import the routing address and rule** (`config/connect`) under *Solution Manager → Integration → IFS Connect*. In the download from AtroNexus the address already points at your AtroNexus. Open `C_ATX_MESSAGE_ADDR` and paste the **hook key** from AtroNexus (*Messaging → Setup*) into the bearer token field.
3. **In AtroNexus**, create a template and wait for WhatsApp to approve it, then a scenario that uses it. Try it with *Send test*.
4. **Call it from IFS.** For example, an event action of type *Execute Online SQL*:
   ```sql
   BEGIN
      C_Atx_Message_Util_API.Send('ORDER_SHIPPED',
         C_Atx_Message_Util_API.Params('phone',        '&PHONE',
                                       'customerName', '&CUSTOMER_NAME',
                                       'orderNo',      '&ORDER_NO'));
   END;
   ```
   `Params` takes up to ten name/value pairs and escapes them. For more, or for numbers and nested values, pass your own JSON text instead. `Send` never raises: if something is wrong it writes to the trace, so the user's own action still goes through. Use `Send_Or_Fail` where an error should stop the transaction.

## Phone numbers

Send the number as IFS has it. `+94 77 123 4567` and `0094771234567` always work. A local number like `0771234567` needs the **default country code** set in AtroNexus (*Messaging → Setup*).

## Message to AtroNexus (version 1)

`POST https://atronexus.atrum0x.com/api/hooks/ifs/messages` with `Authorization: Bearer <hook key>`:

```json
{
  "version": 1,
  "scenario": "ORDER_SHIPPED",
  "params": { "phone": "0771234567", "customerName": "Acme", "orderNo": "C1001" },
  "messageId": "8f1c0e6b5a7d4e2f9a3b1c0d2e4f6a8b"
}
```

## WhatsApp rules to know

- Messages a business starts must use a template WhatsApp approved. Approval usually takes minutes, sometimes a day.
- People must have agreed to get WhatsApp messages from you.
- Every message costs money (WhatsApp charges per message, by category and country). AtroNexus counts each one.
- For now messages come from the AtroNexus WhatsApp number. Sending from your own company number is planned.
