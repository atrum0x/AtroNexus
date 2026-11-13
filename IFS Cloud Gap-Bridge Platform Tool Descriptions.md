# IFS Cloud Gap-Bridge Platform: Tool Descriptions

Nov 12, 2026 · @Yuki

## Overview

The platform is a set of seven small tools that do things IFS Cloud cannot do by itself, each connected to IFS through its REST API. Every tool follows the same idea: IFS calls the tool, the tool does the missing job, and the tool sends the result back into IFS.

Each gap below was found in IFS documentation or in questions on the IFS Community. Some threads are a few years old, so each gap should be checked on the target IFS release before building.

### The shared pattern

1. Something happens in IFS: a user clicks a button, or an event fires.
2. IFS calls the tool, or opens the tool's page, with a reference to the record.
3. The tool does the job IFS cannot do, such as asking a browser for its location or sending a WhatsApp message.
4. The tool writes the result back to IFS through the REST API.
5. IFS carries on with its normal logic, such as validations, events and status changes.

### The seven tools

| # | Tool | Gap it fills | Main users |
| --- | --- | --- | --- |
| 1 | Capture page | The web client cannot read the user's location, IP address or device | Staff working in the browser |
| 2 | Messaging hub | No built-in WhatsApp or SMS sending | Customers, suppliers, staff |
| 3 | Approve from email or chat | Approvals need a login or the Notify Me app | Managers and approvers |
| 4 | Email in, record out | An incoming email cannot create an IFS record | Service desks, customers |
| 5 | Guest links and forms | People without an IFS login cannot see or submit anything | Contractors, customers |
| 6 | SharePoint and OneDrive documents | No direct link between IFS documents and SharePoint | Any team using Microsoft 365 |
| 7 | Configuration change tracker | No audit trail for configuration changes | IFS administrators |

## 1. Capture page

A small web page, opened from a button in IFS, that reads the user's location, IP address and device details from the browser and saves them on an IFS record.

### The gap

IFS Cloud has device location only in its mobile apps, where it is [a documented feature](https://docs.ifs.com/techdocs/24r2/060_development/022_user_interface/035_native/020_native_features/010_device_location_functionality/). The browser client has nothing similar, and custom JavaScript cannot run inside an IFS page. IFS Workflows do not help either: their scripts run on the server, so they see the server and not the user's device, as an [IFS Community thread on reading the client IP address](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/working-on-a-workflow-to-get-the-clients-ip-address-52764) explains.

### How it works

1. The user clicks a custom command in IFS, for example "Capture my location".
2. IFS opens the capture page with a one-time request ID in the address.
3. The browser asks the user to allow location access.
4. The page sends the latitude, longitude, accuracy, IP address and browser details to the tool's backend.
5. The backend writes them to IFS against the request ID.
6. A custom event in IFS copies the values to the real record, or raises an error if the location is not acceptable.

### Example

A storekeeper clicks "Confirm receipt" on a purchase order receipt. A tab opens for a couple of seconds and shows "Location captured". Back in IFS, the receipt now shows the coordinates and the time they were taken.

### What to build

| Part | What it is |
| --- | --- |
| Capture page | One HTML and JavaScript page served over HTTPS |
| Backend | A small service that receives the data and calls IFS with a service user |
| IFS package | A custom entity for capture requests, a custom command and a custom event |

### Things to know

- Browsers only give location to pages served over HTTPS.
- The user can refuse, so IFS needs a rule for what happens then.
- Accuracy is good on phones and can be off by kilometres on desktop PCs.
- Browser location can be faked, so it is evidence of convenience, not proof.

## 2. Messaging hub

One service that IFS calls whenever it needs to send a WhatsApp, SMS or similar message, so IFS never has to know about individual gateways.

### The gap

The old SMS sender in IFS is no longer supported, and the suggested replacement is to call an outside gateway over HTTP. An [IFS Community thread asking how to send WhatsApp messages from IFS](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/send-message-from-ifs-to-whatsapp-person-or-group-19793) got exactly that answer. Every customer therefore builds their own connection to their own gateway.

### How it works

1. An event fires in IFS, for example a work task is assigned or an invoice becomes overdue.
2. The event action calls the hub with a template name, the recipient and the values to fill in.
3. The hub builds the message from the template and sends it through the right channel.
4. The hub records the delivery status and can write it back to IFS.

### Examples

- A technician gets a WhatsApp message each morning listing the day's work tasks.
- A customer gets an SMS when their order is delivered.
- A customer gets a reminder a few days before an invoice is due.

### What to build

| Part | What it is |
| --- | --- |
| Send API | One endpoint that IFS event actions call |
| Templates | Message texts with placeholders, managed outside IFS |
| Channel connectors | WhatsApp Business, local SMS gateways, email |
| Message log | What was sent, to whom, and whether it arrived |
| IFS package | Ready-made events and event actions for common cases |

### Things to know

- WhatsApp Business messages that a company starts must use templates approved in advance, and recipients must have opted in.
- Every message costs money, so the hub needs per-customer usage counts.
- Local SMS gateways differ by country, which is where a local provider has an advantage.
- The hub is reused by tools 3, 4 and 5, so it is worth building early.

## 3. Approve from email or chat

Approvers receive a message with Approve and Reject links and can decide without opening IFS.

### The gap

A customer asked on the IFS Community for [purchase order approval straight from an email](https://community.ifs.com/buying-procurement-demand-planner-asc-srm-41/approve-of-po-s-by-email-app10-exchange-42789), using the Yes and No buttons in Outlook. A partner [replied that standard functionality cannot do this](https://community.ifs.com/questions/33945) and that the Notify Me mobile app is the usual route. Approvers who rarely use IFS still have to install an app or log in.

### How it works

1. An approval step is created in IFS, for example on a purchase order.
2. An IFS event calls the tool with the approver and a short summary of the document.
3. The tool creates one-time Approve and Reject links and sends them by email or WhatsApp through the messaging hub.
4. The approver clicks a link and confirms on a simple page.
5. The tool records the decision in IFS and the approval step moves on.
6. The approver sees a confirmation, and the requester can be notified.

### Example

A finance manager is travelling and gets a WhatsApp message: "Purchase order for office supplies from supplier X is waiting for your approval." She taps Approve, confirms, and the order is released in IFS a few seconds later.

### What to build

| Part | What it is |
| --- | --- |
| Link service | Creates signed, expiring, one-time links tied to one approver and one step |
| Decision page | Shows the summary and asks for confirmation |
| IFS connector | Authorises or rejects the step through the REST API |
| IFS package | Events on the approval steps that should be covered |

### Things to know

- A link is a key, so links must expire, work once, and belong to one approver.
- High-value approvals should ask for a PIN or a sign-in as well as the link.
- IFS must still show who really approved. Acting for a user through a service account needs a clear audit trail.
- Notify Me already covers approvals for customers happy to use an app, so this tool is for those who are not.

## 4. Email in, record out

A listener watches a shared mailbox and turns each incoming email into an IFS record, such as a case, a service request or a work order, with the email attached.

### The gap

People regularly ask how to create an IFS record from an incoming email, most recently in a [December 2025 thread about creating a case from a mail](https://community.ifs.com/field-service-management-fsm-planning-and-scheduling-optimization-pso-249/create-a-case-from-a-mail-64127). A customer who built this themselves [explains the reason](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/automatic-case-creation-via-email-546): an email arriving at an outside mail server cannot trigger anything in IFS unless something sits in between.

### How it works

1. A customer sends an email to a shared address, for example support@company.
2. The listener picks up the new email.
3. It matches the sender's address to a customer or contact in IFS.
4. It creates the record through the REST API, using rules for each mailbox.
5. It attaches the original email and its attachments to the record.
6. It replies to the sender with the reference number.
7. Later replies in the same conversation are added to the existing record.

### Example

A customer emails a photo of a leaking pump to the support address. Within a minute a case exists in IFS with the photo attached, and the customer has a reply giving the case number.

### What to build

| Part | What it is |
| --- | --- |
| Mailbox connector | Reads Microsoft 365, Gmail or IMAP mailboxes |
| Rules | Which mailbox creates which record type, with which defaults |
| Sender matching | Finds the customer or contact from the email address |
| IFS connector | Creates the record and attaches the email |
| Review queue | Holds emails from unknown senders for a person to check |

### Things to know

- Spam and auto-replies must be filtered out, or they become records.
- Reply detection matters, or one conversation becomes many cases.
- Unknown senders need a clear rule: reject, queue for review, or create under a general customer.

## 5. Guest links and forms

A secure, expiring link lets someone without an IFS login view one document or fill in one form, and the result lands in IFS. This tool carries a licensing caution, described below, that must be cleared before it is sold.

### The gap

A customer asked on the IFS Community whether [documents could be opened through public links](https://community.ifs.com/document-management-docman-248/public-access-to-ifs-documents-via-links-is-it-possible-55921) without an IFS account. The reply was that this is not possible and is a hard problem in an application built around access control. The IFS B2B portal is also narrow: a [thread on customer portals](https://community.ifs.com/field-service-management-fsm-planning-and-scheduling-optimization-pso-249/service-management-customer-portals-60066) notes it covers work orders only, while customers want a simple page for invoices and documents.

### How it works

1. An IFS user or event asks the tool for a guest link to one document or one form.
2. The tool creates a link that expires and is tied to that single item.
3. The link is sent to the outside person by email or WhatsApp.
4. The person opens it and views the document, or fills in and submits the form.
5. The tool writes the submission to IFS, or logs that the document was viewed.
6. The link stops working after use or after its expiry time.

### Examples

- A contractor receives a link, fills in a site inspection form on a phone, and the answers appear on the work task.
- A customer receives a link to download a copy of an invoice.

### What to build

| Part | What it is |
| --- | --- |
| Link service | The same signed, expiring links used for approvals |
| Document viewer | Shows one document fetched from IFS for that link only |
| Form builder | Defines simple forms and maps their fields to IFS |
| IFS connector | Reads the document or writes the submission |
| Access log | Who opened which link and when |

### Caution

- **Licensing.** Outsiders reaching IFS data through a service user may count as external or indirect access under the IFS licence. This must be confirmed with IFS, in writing, before the tool is offered to customers.
- **Data exposure.** Each link must show one item only, never a list or a search.
- **Link safety.** Links must expire, be hard to guess, and be revocable by the IFS user who created them.

## 6. SharePoint and OneDrive documents

Users attach a SharePoint or OneDrive file to an IFS record with a file picker, and can optionally have IFS documents copied out to SharePoint.

### The gap

IFS stores documents in its own repositories. Asked about [dragging a file from SharePoint into IFS](https://community.ifs.com/document-management-docman-248/drag-and-drop-file-from-sharepoint-to-ifs-57932), IFS answered that there is no direct integration and suggested pasting the SharePoint link into a free text field. Another thread confirms that [SharePoint cannot be used as a Document Management repository](https://community.ifs.com/document-management-docman-248/is-it-possible-to-use-sharepoint-as-a-docman-repository-in-ifs-cloud-22058). Companies that keep their files in Microsoft 365 end up with two disconnected places.

### How it works

1. The user clicks "Attach from SharePoint" on an IFS record.
2. A picker page opens and the user signs in with their Microsoft account.
3. The user chooses a file.
4. The tool saves the file's ID, name and link against the IFS record.
5. The file appears in a list on the IFS page, with a link that opens it in SharePoint.
6. Optionally, when a document is checked in to IFS, the tool copies it to a SharePoint folder for that record.

### Example

A project engineer attaches the latest drawing from the team's SharePoint site to a project activity. Colleagues open it from IFS and always get the current version, because the file itself never left SharePoint.

### What to build

| Part | What it is |
| --- | --- |
| File picker page | Lets the user browse and choose a file after Microsoft sign-in |
| Microsoft connector | Talks to SharePoint and OneDrive through Microsoft Graph |
| IFS package | A custom entity for linked files, a command and a list on the page |
| Copy-out job | Optional: pushes IFS documents to a SharePoint folder |

### Things to know

- Permissions stay in SharePoint, so a user without access there cannot open the file from IFS either.
- The tool should store the file's ID and not its path, so the link survives a rename or move.
- The customer's Microsoft 365 administrator has to approve the app once.

## 7. Configuration change tracker

The tracker takes regular snapshots of an IFS environment's configurations and shows what changed between them, so an administrator can see what was changed and when.

### The gap

Asked how to see who changed a page configuration and when, the [answer on the IFS Community in May 2026](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/track-page-configuration-changes-66957) was that IFS Cloud has no standard audit trail for it. A separate [thread on audit trail capability](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/ifs-audit-trail-capability-62325) adds that the code inside event actions and quick reports cannot be history-logged, because of how those fields are stored. When a configuration breaks, administrators have little to go on.

### How it works

1. On a schedule, the tracker reads the configurations from IFS through the REST API.
2. It stores each one as a snapshot with the time it was taken.
3. It compares the new snapshot with the previous one.
4. It lists every difference: what was added, removed or edited.
5. It can alert the administrator when something important changes.
6. The administrator can export an earlier version to restore it.

### What it would track

- Page configurations
- Custom events and event actions, including their code
- Quick reports, including their SQL
- Custom fields and custom entities
- Workflows

### Example

On Monday a field is missing from the customer order page. The administrator opens the tracker and sees the page configuration changed on Friday afternoon, with the field removed. She exports Thursday's version and restores it.

### What to build

| Part | What it is |
| --- | --- |
| Snapshot job | Reads configurations from IFS on a schedule |
| Snapshot store | Keeps every version securely |
| Compare view | Shows two versions side by side with differences marked |
| Alerts | Notifies by email or through the messaging hub |

### Things to know

- "Who" depends on what IFS exposes. If a configuration carries no modified-by value, the tracker can only say when the change happened, to within one snapshot interval. This needs checking early.
- The tracker only reads from IFS, which makes it the safest tool of the seven to install.
- Snapshots contain SQL and business logic, so they must be stored as carefully as the system itself.

## Shared building blocks and build order

The seven tools share five parts, so each part is built once and reused.

| Building block | What it does | Used by tools |
| --- | --- | --- |
| IFS connector | Calls the IFS REST API with each customer's own service user | All seven |
| Secure links | Creates signed, expiring, one-time links | 1, 3, 5 |
| Message channels | Sends WhatsApp, SMS and email | 2, 3, 4, 5, 7 |
| IFS configuration package | Custom entities, commands and events delivered as a package | 1, 2, 3, 5, 6 |
| Admin console and logs | Per-customer settings, usage and error logs | All seven |

### Suggested build order

1. **Capture page.** It is the smallest tool and proves the full round trip: IFS to tool and back.
2. **Messaging hub.** Three later tools depend on it.
3. **Approve from email or chat.** It reuses secure links and the hub.
4. **Email in, record out.** It adds the mailbox connector.
5. **SharePoint and OneDrive documents.** It adds the Microsoft connector.
6. **Guest links and forms.** It comes late because the licensing question must be settled first.

The configuration change tracker depends on nothing but the IFS connector, so it can be built at any point alongside the others.

## Risks and open questions

Four risks apply to the platform as a whole.

- **IFS may close a gap.** IFS has already added features that were once gaps, such as [automatic currency rate updates](https://docs.ifs.com/ifsclouddocs/23r2/DefineFinancialsBasics/AboutAutomaticCurrencyRate.htm) and [data capture for supplier invoices](https://docs.ifs.com/ifsclouddocs/25r2/lang/en/SupplierInvoicing/AboutDataCaptureforSupplierInvoices.htm). Tools tied to local needs, such as local SMS gateways, are safer than generic ones.
- **Licensing.** Any tool that lets outsiders reach IFS data needs IFS's confirmation. This affects tool 5 most, and tool 3 to a lesser degree.
- **Customer credentials.** The platform holds a service user for every customer's IFS environment, which makes it a target. Credentials must be encrypted and each customer's data kept separate.
- **Age of the evidence.** Some community threads are several years old. Each gap must be re-tested on the IFS release the first customer runs.

### Open questions

- [ ] Does the IFS licence allow guest access through a service user, and on what terms?
- [ ] Which IFS releases will the platform support first?
- [ ] Which WhatsApp and SMS providers will the messaging hub use?
- [ ] Does IFS expose who last modified each configuration type, for the change tracker?
- [ ] Will the platform be hosted once for all customers, or installed per customer?

## Sources

- [IFS Community: workflow to get the client's IP address](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/working-on-a-workflow-to-get-the-clients-ip-address-52764)
- [IFS docs: device location functionality in mobile apps (24R2)](https://docs.ifs.com/techdocs/24r2/060_development/022_user_interface/035_native/020_native_features/010_device_location_functionality/)
- [IFS Community: send message from IFS to WhatsApp](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/send-message-from-ifs-to-whatsapp-person-or-group-19793)
- [IFS Community: approve purchase orders by email (request)](https://community.ifs.com/buying-procurement-demand-planner-asc-srm-41/approve-of-po-s-by-email-app10-exchange-42789)
- [IFS Community: approve purchase orders by email (partner reply)](https://community.ifs.com/questions/33945)
- [IFS Community: automatic case creation via email](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/automatic-case-creation-via-email-546)
- [IFS Community: create a case from a mail](https://community.ifs.com/field-service-management-fsm-planning-and-scheduling-optimization-pso-249/create-a-case-from-a-mail-64127)
- [IFS Community: public access to IFS documents via links](https://community.ifs.com/document-management-docman-248/public-access-to-ifs-documents-via-links-is-it-possible-55921)
- [IFS Community: service management customer portals](https://community.ifs.com/field-service-management-fsm-planning-and-scheduling-optimization-pso-249/service-management-customer-portals-60066)
- [IFS Community: drag and drop file from SharePoint to IFS](https://community.ifs.com/document-management-docman-248/drag-and-drop-file-from-sharepoint-to-ifs-57932)
- [IFS Community: SharePoint as a Docman repository](https://community.ifs.com/document-management-docman-248/is-it-possible-to-use-sharepoint-as-a-docman-repository-in-ifs-cloud-22058)
- [IFS Community: track page configuration changes](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/track-page-configuration-changes-66957)
- [IFS Community: IFS audit trail capability](https://community.ifs.com/framework-experience-infrastructure-cloud-integration-dev-tools-50/ifs-audit-trail-capability-62325)
- [IFS docs: automatic update of currency rates](https://docs.ifs.com/ifsclouddocs/23r2/DefineFinancialsBasics/AboutAutomaticCurrencyRate.htm)
- [IFS docs: data capture for supplier invoices](https://docs.ifs.com/ifsclouddocs/25r2/lang/en/SupplierInvoicing/AboutDataCaptureforSupplierInvoices.htm)
