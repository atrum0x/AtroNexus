# AtroNexus progress notes

What has been built so far, why, and what's still open. Last updated 14 November 2026. For how to run and deploy, see `README.md`. For conventions to follow when changing the code, see `CLAUDE.md`.

## Where things run

| Part | Where | Notes |
| --- | --- | --- |
| Frontend | Vercel, https://atro-nexus.vercel.app | Next.js 16, root directory `frontend` |
| Backend | Northflank, `p01--atronexusdev--5m85wmw9smjn.code.run` | FastAPI, built from `backend/Dockerfile` |
| Database | Neon (Postgres, `eu-west-2`, pooled host) | Schema managed by Alembic, upgraded on backend start |
| Code | GitHub `atrum0x/AtroNexus`, branch `main` | Every change goes through a pull request |

Only the Vercel frontend can call the backend: every request must carry the shared `INTERNAL_API_KEY` (except `/api/health`).

## Timeline

| # | What | Commit / PR |
| --- | --- | --- |
| 1 | Login (FastAPI + JWT, Next.js + shadcn), Orval-generated API client, fonts fixed | `676ba17`, PR #1 |
| 2 | IFS connector: OAuth2 client credentials or basic auth, encrypted secrets, test button | PR #1 |
| 3 | Tool 1, the capture page: link from IFS, reads location/IP/device, writes back to IFS | PR #1 |
| 4 | Hosting: Vercel + Northflank + Neon, internal API key, client IP passed safely | PR #1 |
| 5 | Sign-in error on the live site explained, `API_URL` mistakes forgiven | `ac0e58c` |
| 6 | Capture page made reliable on Android and iPhone | `6895ad7` |
| 7 | `:text` placeholders for IFS text attributes | `9fea63a` |
| 8 | SaaS step 1: organizations and data separation, Alembic | PR #2 |
| 9 | SaaS step 2: sign-up, email sign-in, email verification, password reset | PR #3 |
| 10 | SaaS step 3: team invitations and roles | PR #4 |
| 11 | SaaS step 4: tools switched on and off per organization | PR #5 |
| 12 | Progress notes (this file) | PR #5 |
| 13 | SaaS step 5: usage counting and the overview dashboard | PR #6 |
| 14 | SaaS step 6: platform admin | PR #7 |
| 15 | SaaS step 7 (part): IFS addresses must be public (SSRF guard) | PR #8 |
| 16 | Sidebar navigation (shadcn) | PR #9 |
| 17 | Light/dark mode, sharper headings, capture page polish | PR #10 |
| 18 | Custom domain atrum0x.com, real email through Resend | settings only |
| 19 | Capture links: rate limits and a New link button | PR #11 |
| 20 | Tool 3: approvals from email (purchase requisition lines) + IFS package | PR #12 |
| 21 | IFS package download on the Approvals page; approval types (pick which approvals; PR lines built, five more as coming soon) | PR #13 |
| 22 | Tool 2: messaging hub, WhatsApp templates and scenarios called from any IFS event | PR #15 |

## 1. Foundations

- **Backend:** FastAPI, SQLAlchemy 2, PyJWT, argon2 password hashes (pwdlib), managed with `uv`. Tests with pytest; they run on SQLite and on Postgres (via PGlite locally).
- **Frontend:** Next.js 16 with Cache Components, Tailwind v4, shadcn/ui (`base-nova` style on Base UI). The session JWT lives in an HttpOnly cookie (`atx_session`), so only server code (server actions and components) calls the API.
- **Orval:** `npm run gen:api` writes `openapi.json` straight from the FastAPI app and generates plain fetch functions into `src/api/generated/`. Function names come from the backend handler names.
- **Fonts:** `shadcn init` had written `--font-sans: var(--font-sans)`, which silently fell back to serif. It now points at Geist.

## 2. IFS connector (`backend/app/ifs/`)

- One connection per IFS environment and service user. Supports OAuth2 client credentials (IFS Cloud's default; tokens cached until shortly before expiry) and basic auth.
- Secrets are encrypted with Fernet (`ENCRYPTION_KEY`) and never returned by the API.
- TLS uses the operating system's trust store (`truststore`). DSS UAT sends only its leaf certificate; Windows fetches the missing intermediate, Linux doesn't, so the Docker image installs `backend/certs/*.crt` (the Sectigo intermediate is there). Verification is never turned off.
- Problems solved on the way: `CERTIFICATE_VERIFY_FAILED` (fixed as above), and `401 invalid_client` (the client ID is case-sensitive: `AtroNexus`).

## 3. Tool 1: capture page

- A **capture page** (target) says which connection to use, the IFS endpoint path, PATCH or POST, and a JSON body template with placeholders such as `{latitude}`, `{ip}`, `{device}`.
- The link for an IFS custom command is `/c/<public id>/<request id>`. The page asks the browser for its location and sends it, with IP and device details, to IFS.
- A request ID can be sent once; a failed attempt can be retried.
- **PATCH** reads the record first (a 404 means the request ID doesn't exist in IFS) and sends its ETag as `If-Match`. **POST** creates a record.
- **Phones:** help text matches the device (Safari on iPhone, Chrome on Android); GPS falls back to a quicker network location indoors; in-app browsers (WhatsApp, Teams, Outlook) are told to open the link in Safari or Chrome; "Continue without location" appears after 12 seconds.
- **`:text` placeholders:** a value that is exactly one placeholder keeps its type, so `"{latitude}"` is sent as a number. IFS rejects numbers for text (`Edm.String`) attributes with "Malformed Request", so write `"{latitude:text}"` for those.
- **What we learned from the real IFS projection** `CustomProjectionCLocationCapture.svc/CLocationCaptureSet`: the key is `Objkey`, every `Cf_*` attribute is text (100 characters), and the request ID is text. On `putedar-dev1` this body works:

  ```json
  {
    "Cf_Accuracy": "{accuracy:text}",
    "Cf_Device": "{device}",
    "Cf_Ip_Address": "{ip}",
    "Cf_Latitude": "{latitude:text}",
    "Cf_Longitude": "{longitude:text}",
    "Cf_Request_Id": "{request_id}",
    "Cf_Status": "{status}"
  }
  ```

## 4. Hosting

- Backend on Northflank from the Dockerfile; Uvicorn runs without `--proxy-headers` on purpose.
- The browser's IP comes from Vercel's `x-real-ip` and travels as `X-Client-IP`; the backend trusts it only together with the internal key.
- Neon is used through its pooled (PgBouncer) host, so prepared statements are switched off (`prepare_threshold=None`).
- Live sign-in failed at first because of the Vercel environment variables. `API_URL` now gets `https://` added and a trailing `/` removed, and the login form says which problem it is.

## 5. SaaS steps 1 to 6

The plan: customers sign up themselves, each company has its own space and dashboard, and pays a monthly fee per tool (plus usage where a tool has a real cost per use). Payments come later.

### Step 1: organizations (PR #2)

- Every customer is an `Organization`. Users, IFS connections and capture pages belong to one; captures belong through their capture page.
- Every admin endpoint only sees its own organization's rows. Another organization's rows answer 404, and a capture page can't use another organization's connection (that would mean using another customer's IFS credentials).
- A suspended organization can't sign in and its capture links stop working.
- **Alembic** now manages the schema and runs on backend start. The live database was upgraded in place: the existing user, connections and capture pages moved into an "AtroNexus" organization, and `admin` became its owner and the platform admin.

### Step 2: accounts (PR #3)

- **Sign-up** (`/signup`) creates an organization with the new user as owner, signs them in and emails a confirmation link.
- Until the email is confirmed, the user can look around but can't save or test IFS connections or capture pages.
- **Sign-in uses the email address.** Older accounts like `admin` can still use their username; `ADMIN_EMAIL` gives the admin an email.
- **Forgot password** emails a one-time reset link (1 hour). A reset signs the user out everywhere else.
- Email links are stored only as hashes.
- **Emails aren't sent yet:** `EMAIL_BACKEND=console` writes them, with their links, to the backend log. Resend is wired in for when there's a sending domain.

### Step 3: team (PR #4)

- **Team page** (`/team`): members with a role dropdown and remove, pending invitations with cancel, and an invite form.
- **Invitations:** one-time link, 7 days, accepted on `/invite`. The new account gets the invited role and a confirmed email.
- **Roles:** owner (everything), admin (connections, capture pages and the team, but not owners), member (looks at everything, changes nothing). Members see settings read-only.
- **Rules:** nobody changes or removes themselves, only owners touch owners, an organization keeps at least one owner, and an email that already has an account can't be invited (one organization per account for now).

### Step 4: tools (PR #5)

- **Tools page** (`/tools`): all seven tools with **placeholder** prices. Only the capture page is built; the others say "Coming soon".
- Owners and admins switch tools on and off. Every switch is logged with who and when (`tool_events`), which billing will use.
- A tool that's off disappears from the menu and home page, its pages say it's switched off, and its public links stop working. Settings and history are kept.
- New sign-ups start with no tools. Existing organizations kept the capture page on.

| Tool | Placeholder price |
| --- | --- |
| Capture page | $29 / month |
| Messaging hub | $49 / month + $0.02 per message |
| Approve from email or chat | $39 / month |
| Email in, record out | $29 / month |
| Guest links and forms | $49 / month |
| SharePoint and OneDrive documents | $39 / month |
| Configuration change tracker | $59 / month |

### Step 5: usage and dashboard (PR #6)

- **Usage records** (`usage_events`): one row per counted use, saved together with the action. A capture sent to IFS counts as billable; a failed one is recorded but never billable. Rows are never changed, so any month can be recalculated.
- **History:** existing captures were backfilled when the table was created, so the numbers start with real data.
- **Dashboard** (the home page):
  - a setup checklist (confirm email, switch on a tool, add a connection, create a capture page, invite the team) until it's all done
  - usage per tool for the current month, with failures and last month for comparison
  - the latest errors, each linking to where to fix it
  - for owners and admins, an estimated cost for the month: the monthly fees of switched-on tools plus usage at the per-use price (placeholder prices; nothing charged)
- Months are calendar months in UTC.

### Step 6: platform admin (PR #7)

- **Platform section** (`/platform`), only for the platform admin. Anyone else gets a "not found" page, and the API answers 404 rather than "forbidden".
- **Overview:** totals across all customers (customers, active and suspended, users, usage this month, estimated monthly revenue at placeholder prices) and a table of every organization with owner, members, tools, usage and estimated revenue.
- **Customer detail:** members (with unconfirmed emails marked), tools with usage this month and last, the on/off history with who switched, counts of connections and capture pages, and recent errors.
- **Suspend and reactivate**, with an optional reason that only the platform admin sees. Suspending blocks sign-in, ends sessions and stops the customer's links; nothing is deleted. The platform's own organization can't be suspended.
- Fixed during testing: the suspend dialog now closes after it succeeds, and always sends the status shown on the button.

### Step 7, first part: internal addresses blocked (PR #8)

- Customers type their own IFS addresses, so the backend refuses any that would make it call an internal network: localhost, private ranges, link-local (including the cloud metadata service at `169.254.169.254`), shared/CGNAT, multicast and reserved addresses, in IPv4 and IPv6. Addresses must use `https://`.
- Checked when a connection is saved (a clear error message) and again before every call to IFS, since a name can resolve differently later. Redirects aren't followed.
- The live connections (DSS UAT and putedar-dev1) were checked with real DNS before release and pass.
- `ALLOW_PRIVATE_IFS_URLS=true` turns the check off for local development with a fake IFS.
- Known gap: a DNS server that changes its answer in the split second between the check and the connection (DNS rebinding). Closing it means connecting to the checked IP directly.
- The rest of step 7 (rate limits, a sign-up CAPTCHA) is left for later, as decided.

## 6. Interface

- **Sidebar** (PR #9), based on shadcn's `sidebar-07`: the AtroNexus mark and organization at the top; Dashboard; a Tools section (Capture pages while it's on, All tools); an Organization section (IFS connections, Team); Platform → Customers for the platform admin; the signed-in user at the bottom with a menu (organization, role, Sign out). It collapses to icons with the header button or Ctrl/Cmd+B and stays collapsed while you move between pages; on phones it's a drawer that closes after you pick a page. A slim header shows the collapse button and a breadcrumb.

- **Light/dark mode** (PR #10): in the sidebar's user menu, under Appearance: Light, Dark, or Same as device (the default). Remembered in the browser. The public capture page and the sign-in pages follow it too.
- **Headings:** every page title is larger on wider screens, with a short description and a line under it; the dashboard uses the same heading.
- **Capture page on phones:** the AtroNexus mark above the card, a coloured status circle (blue while looking, green when saved, amber without a location, red when IFS refused), larger headings, full-width buttons at least 44px tall, and room for the iPhone home bar.

## 7. Domain, email and capture link safety

- **Domain:** `atrum0x.com` (DNS on Cloudflare). The app runs at `https://atronexus.atrum0x.com` on Vercel. Email goes out through Resend from `no-reply-atronexus@atrum0x.com` (DKIM, SPF on `send.atrum0x.com`, DMARC set up). The admin account's email was corrected to `senujajayasekara@gmail.com`.
- **Keep the `atronexus` DNS record "DNS only" (grey cloud) in Cloudflare.** Proxied through Cloudflare, Vercel would see Cloudflare's IP instead of the visitor's, and the capture page would save the wrong IP.
- **Capture links (PR #11):** rate limits on the public capture endpoints (opening: 60/min per visitor; submitting: 10/min and 60/hour per visitor, 300/hour per capture page in total), a friendly "Too many attempts" page, and a **New link** button on each capture page that changes its address so every old link stops working (then update the IFS custom command).
- **Still open for capture links:** links are shared per capture page, so one leaked link works for any request ID until renewed. The proper fix is one-time links per request (IFS asks AtroNexus for a link when it creates the request), planned with the secure-links building block for the approvals tool. Optional extra: only accept a capture while the IFS record's status still says it's waiting for one (PATCH targets only).

## 8. Tool 3: approvals from email (PR #12)

**Research behind it** (your DSS and tea_int work, the 25.1 core files):
- IFS → AtroNexus uses the pattern from the GRN status integration: event action → PL/SQL → `Plsqlap_Server_API.Post_Outbound_Message` → routing rule → REST routing address (Bearer auth, as in the Dialog SMS integration).
- IFS ships the event `PUR_REQ_LINE_TO_BE_AUTHORIZED` (also used by Notify Me) with the approver and line details.
- IFS decides who's approving from the logged-in user (`Check_Authorizer`, `Validate_Auth_Limits`), so the service user can't approve for someone. `Fnd_Session_Util_API.Impersonate_Fnd_User_` (system privilege `IMPERSONATE USER`) lets the package run IFS's own authorize and reject as the real person.
- Security checkpoint `PURCH_REQ_AUTHORIZATION` is off on your environment (and by default).

**What was built:**
- **IFS package** `backend/ifs_package/approvals/` (code delivery, no tables): utility + projection `CAtxApprovalHandling`, an event action, routing rule and address, and a README with installation steps and the JSON contract. Tokens are HMAC-SHA256 with a secret only IFS knows, so AtroNexus can only act on approvals IFS asked for, as the person IFS named, within their limits.
- **Secure links** (building block): hashed one-time tokens, expiry, revoke, open/used tracking.
- **AtroNexus**: the hook (through the frontend, Bearer key), approval emails, the public approval page `/a/<token>` (live line from IFS, Approve with a confirm, Reject with IFS reject reasons and a note), the admin page `/approvals` (setup, hook key shown once, IFS package check, request log), usage counting, and the "Approve from email" tool switched on as available.

**Still to do before real use:** build and deploy the IFS package on a test environment (the PL/SQL hasn't been compiled yet), grant the service user `IMPERSONATE USER`, and run one real requisition line end to end. Then purchase orders and change orders (same pattern), reminders, and a code for high-value approvals.

### Package download and approval types (PR #13)

- The Approvals page has a **Download IFS package** button. The zip has the source to build, `config/C_ATX_APPROVALS.zip` ready to import, the README, and the routing rule and address with the address already pointing at that AtroNexus (only the hook key is pasted in). The package moved to `backend/ifs_package/approvals/` because the Docker image only has `backend/`.
- **Approval types**: step 1 on the page is now *Choose approval types*. Purchase requisition lines can be switched on; purchase orders, PO change orders, supplier invoices, expense sheets and document revisions are listed as coming soon. The download only contains the event actions of the types switched on, IFS messages for a type that's off are refused (409), and links of a type that's switched off stop working. Requests are stored with a generic `object_key` instead of requisition columns (migration `0009`; existing setups keep PR lines on), so a new type only needs its IFS code and a catalog entry in `app/approvals/flows.py`.

## Environment variables

**Backend (Northflank):** `DATABASE_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`, `INTERNAL_API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL` (optional), `APP_URL` (the Vercel address, used in email links), `EMAIL_BACKEND` (`console` or `resend`), and with Resend: `RESEND_API_KEY`, `EMAIL_FROM`. `ALLOW_PRIVATE_IFS_URLS` must stay unset (false) in production. For WhatsApp: `WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_DISPLAY_NUMBER`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN`.

**Frontend (Vercel):** `API_URL` (the Northflank address, with `https://`), `INTERNAL_API_KEY` (the same value as on Northflank, never `NEXT_PUBLIC_`).

## 9. Tool 2: messaging hub, WhatsApp (PR #15)

**Why WhatsApp first:** one official API (Meta's WhatsApp Cloud API) for every country and network, buttons in messages, and people actually read it. SMS differs per operator unless a gateway is used, so it comes later.

**What was built:**
- **Templates**: customers write the message with `{{1}}`, `{{2}}` variables, an optional header, footer and up to 3 buttons (links can end with a variable), with a live WhatsApp-style preview. AtroNexus checks Meta's rules first, submits it for review, and the result comes back by webhook (or *Check status now*).
- **Scenarios**: a code IFS calls (e.g. `ORDER_SHIPPED`), the template, who gets it (`{phone}`) and which IFS values fill each variable (`{customerName}`, `Order {orderNo}`, `{customer.name}`). The page shows the PL/SQL to paste into an IFS event action, and *Send test* sends one with typed values.
- **IFS package** (`backend/ifs_package/messaging/`, download on the Messaging page): `C_Atx_Message_Util_API.Send(scenario, Params(...))`, queued through IFS Connect so it leaves on commit and failures wait in Application Messages for a resend (never sent twice).
- **Sending**: local numbers get the organization's default country code; values are tidied the way WhatsApp requires; each sent message counts as billable usage, failures don't. Delivery reports (sent, delivered, read, failed) update the message log.
- **Shared number for now**, behind a seam for customers' own numbers (decided as the next step).

## Where we are (14 November 2026)

Live on Vercel, Northflank and Neon (migration `0009`):
- **Platform:** self-service sign-up, email sign-in and verification, password reset, teams and roles, tools switched on per organization, usage counting and the dashboard, platform admin, the SSRF guard, sidebar, light/dark mode, and real email from `no-reply-atronexus@atrum0x.com`.
- **Tool 1, capture page:** works end to end on putedar-dev1; rate limits and the New link button are in.
- **Tool 2, messaging hub (WhatsApp):** customers write templates and scenarios and call them from any IFS event. Built and tested against a fake Meta API; **needs a WhatsApp account connected** (see Next) before a real message goes out. Sends from one shared AtroNexus number for now.
- **Tool 3, approvals from email:** the whole AtroNexus side works and is tested against a fake IFS. Customers choose approval types (purchase requisition lines built, five types listed as coming soon) and download the IFS package from the Approvals page. **The IFS side has never run on a real IFS.**

## Next

**1. Test approvals on a real IFS (you, when you have time).** On putedar-dev1 (DSS UAT can't be reached from Northflank yet):
1. On the Approvals page, switch on purchase requisition lines, then download the package.
2. Build and deploy the four files in `workspace/purch` (component PURCH, layer Cust). Send any compile errors; the PL/SQL has never been compiled.
3. Add the object property `CAtxApproval / * / HMAC_SECRET` (32+ random characters).
4. Import `config/C_ATX_APPROVALS.zip`, and enable the event `PUR_REQ_LINE_TO_BE_AUTHORIZED`.
5. Import the routing rule and address, and paste the hook key (Approvals step 3) into the address.
6. Give the service user a permission set with the projection `CAtxApprovalHandling` and the system privilege `IMPERSONATE USER`.
7. Approvals step 5: *Check IFS*. Then release a test requisition line that needs authorization, approve it from the email, and confirm IFS shows the approver as the signer. Try a reject too, and an approver over their limit.

If something fails, the places to look are *Application Messages* in IFS (did the message leave, what did AtroNexus answer), the IFS trace, and the request log on the Approvals page.

**2. Connect WhatsApp (you).** Follow "Messaging hub" in `README.md`: a Meta developer app with WhatsApp, its free test number, a system-user token, and the webhook pointing at `https://atro-nexus.vercel.app/api/hooks/meta/whatsapp`. Put the values on Northflank. Then make a template, wait for approval, make a scenario, and *Send test* to your own phone (it must be one of the test number's verified recipients).

**3. Messaging next steps (decided: customers must send from their own numbers):**
- **Customers' own WhatsApp numbers**: AtroNexus becomes a Meta Tech Provider; customers connect their WhatsApp Business account with Embedded Signup on the Messaging page. Needs Meta business verification for AtroNexus. The code already has the seam (`app/messaging/accounts.py`).
- **Approvals on WhatsApp**: an approval type gets a channel (email, WhatsApp or both), using a built-in scenario whose button opens the approval link.
- Incoming replies (quick-reply buttons written back to IFS), SMS through a gateway, message errors on the dashboard.

**4. After the real approvals test works, other options:**
- **More approval types.** Purchase orders and PO change orders first: same pattern, standard events `PUR_ORD_LINE_TO_BE_AUTHORIZED` and `POCO_TO_BE_AUTHORIZED` (re-check them in the core files). Each needs PL/SQL + projection actions, an event action under `flows/<type>/`, and its entry in `app/approvals/flows.py`.
- **Approval extras:** reminder emails for open approvals, and a PIN or sign-in for high-value approvals (the design doc asks for it).
- **Tool 7, configuration change tracker.** Only needs the IFS connector; read-only, so it's lower risk.

**5. Hardening before real customers:**
- Rate limits on sign-in, sign-up and password reset; a CAPTCHA on sign-up.
- Terms of service and privacy pages; payments later (monthly fee per switched-on tool plus usage, from the usage records).
- The licensing question: confirm with IFS in writing that approvals (and later guest links) don't count as indirect access.

**Needs action from you:**
- **Rotate the Neon password.** It was shared in a chat. Reset it in Neon and update `DATABASE_URL` on Northflank.
- **Real tool prices.** They live in `backend/app/tools/catalog.py` (placeholders now).
- **DSS UAT is unreachable from Northflank.** DSS probably allows only certain IP addresses. Options: a static outbound IP on Northflank that DSS allows, or a relay inside an allowed network. `putedar-dev1` works.

**Possible capture page improvements that were discussed:**
- More device placeholders (browser and version, device type, OS version).
- Switch the DSS target to PATCH with `{request_id}` as the `Objkey`, so IFS checks the request exists; optionally accept only requests whose IFS status is still waiting for capture.
- One-time links per request instead of one shared link per capture page (the secure-links block can do it now).
- A CA certificate field per connection, instead of adding certificates to the Docker image.

## Lessons for working on this repo

- **The local dev backend reloads on every file change** and runs migrations on start. Write and test a new migration outside `migrations/` first, then move it in, or the local database can end up half-migrated (this happened once and was repaired).
- **On Windows, stopping a background server can leave its child process running** on the port. Test servers ran on ports 3100 and 8100 with their own database and were stopped by process, not just by task.
- **Every new model module** must be imported in `app/models_registry.py`; `test_migrations_match_the_models` fails when a model change has no migration.
