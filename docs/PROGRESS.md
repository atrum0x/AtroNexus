# AtroNexus progress notes

What has been built so far, why, and what's still open. Last updated 13 November 2026. For how to run and deploy, see `README.md`. For conventions to follow when changing the code, see `CLAUDE.md`.

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

## Environment variables

**Backend (Northflank):** `DATABASE_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`, `INTERNAL_API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL` (optional), `APP_URL` (the Vercel address, used in email links), `EMAIL_BACKEND` (`console` or `resend`), and with Resend: `RESEND_API_KEY`, `EMAIL_FROM`.

**Frontend (Vercel):** `API_URL` (the Northflank address, with `https://`), `INTERNAL_API_KEY` (the same value as on Northflank, never `NEXT_PUBLIC_`).

## Open items

**Needs action from you:**

- **Rotate the Neon password.** It was shared in a chat. Reset it in Neon and update `DATABASE_URL` on Northflank.
- **A sending domain** for email (Resend). Until then, confirmation, reset and invitation links are only in the Northflank backend log.
- **Real tool prices.** They live in `backend/app/tools/catalog.py`.
- **DSS UAT is unreachable from Northflank.** Connections time out; DSS probably allows only certain IP addresses. Options: a static outbound IP on Northflank that DSS allows, or a relay inside an allowed network. `putedar-dev1` works.

**Next SaaS steps:**

5. ~~Usage counting and an overview dashboard per organization.~~ Done in PR #6.
6. ~~Platform admin view: every customer, their tools and usage, suspending a customer.~~ Done in PR #7.
7. Hardening: block internal addresses as IFS URLs (SSRF), rate limits on sign-in, sign-up and public endpoints, a CAPTCHA on sign-up.

Later: payments (monthly subscription per switched-on tool, usage billed from the usage records), terms of service and privacy pages before public sign-up.

**Possible capture page improvements that were discussed:**

- More device placeholders (browser and version, device type, OS version).
- Switch the DSS target to PATCH with `{request_id}` as the `Objkey`, so IFS checks the request exists.
- A CA certificate field per connection, instead of adding certificates to the Docker image.

**After the capture page, the planned tool order:** messaging hub (needed by approvals, email-in and guest links), approvals, email-in, SharePoint, guest links. The change tracker only needs the IFS connector and can come at any time. Recommendation made: build approvals by email next, since it reuses the capture page's round trip and brings the secure-links and email building blocks with it.

## Lessons for working on this repo

- **The local dev backend reloads on every file change** and runs migrations on start. Write and test a new migration outside `migrations/` first, then move it in, or the local database can end up half-migrated (this happened once and was repaired).
- **On Windows, stopping a background server can leave its child process running** on the port. Test servers ran on ports 3100 and 8100 with their own database and were stopped by process, not just by task.
- **Every new model module** must be imported in `app/models_registry.py`; `test_migrations_match_the_models` fails when a model change has no migration.
