# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Built: login, the IFS connector (shared building block), tool 1 (the capture page), tool 3 (approvals from email, purchase requisition lines; see below), the secure-links building block, and SaaS steps 1 (organizations and data separation), 2 (self-service sign-up, email sign-in, email verification, password reset), 3 (team invites and roles), 4 (per-tool switches), 5 (usage counting and the overview dashboard) and 6 (platform admin), and the SSRF guard from step 7. Still open from step 7: rate limits and a sign-up CAPTCHA. No payments yet; pricing will be a monthly fee per tool, plus usage where a tool needs it. The design document `IFS Cloud Gap-Bridge Platform Tool Descriptions.md` is the source of truth for what gets built.

## Stack and commands

- `backend/`: FastAPI, SQLAlchemy (SQLite by default), PyJWT, pwdlib (argon2), managed with `uv`. Copy `.env.example` to `.env` first; `JWT_SECRET` (32+ chars) and `ENCRYPTION_KEY` (a Fernet key, encrypts stored IFS secrets; changing it makes them unreadable) are required. `ADMIN_USERNAME`/`ADMIN_PASSWORD` seed a user on startup if it doesn't exist. The schema is managed by Alembic (`backend/migrations/`), and the app runs `upgrade head` on startup (`app/migrate.py`). A database from before migrations (tables but no version) is stamped at `0001`, which matches that original schema. After changing a model: `uv run alembic revision --autogenerate -m "..."`, then fix the file by hand where existing rows need data (see `0002_organizations.py`: add nullable, fill, then NOT NULL). A new model module must be imported in `app/models_registry.py`. `test_migrations_match_the_models` fails when a model change has no migration. `DATABASE_URL` takes SQLite (local default) or Postgres; production uses Neon through its pooled (`-pooler`, PgBouncer) host. `app/db.py` rewrites `postgres://` URLs to the psycopg driver and sets `prepare_threshold=None`, because prepared statements break behind a transaction pooler. Keep that. Run the tests against Postgres with `TEST_DATABASE_URL=postgres://... uv run pytest` (they drop all tables, including `alembic_version`). They pass on Postgres 18 via PGlite (`npx @electric-sql/pglite-socket`), but no test has run against Neon itself.

## Deployment

Frontend on Vercel (root directory `frontend`), backend on Northflank (built from `backend/Dockerfile`). Steps are in `README.md`. Because the backend has a public address, `app/internal.py` refuses every request without `X-Internal-Key` = `INTERNAL_API_KEY` (except `/api/health`), and the frontend's mutator sends it. The browser IP travels as `X-Client-IP`: the capture server action takes it from Vercel's `x-real-ip` (falling back to the last `x-forwarded-for` entry locally), and the backend only trusts it with a valid key, or from loopback when no key is configured. Uvicorn runs without `--proxy-headers` on purpose. Never expose `INTERNAL_API_KEY` as `NEXT_PUBLIC_*`.
  ```bash
  uv run uvicorn app.main:app --reload --port 8000   # API, docs at /docs
  uv run pytest                                      # tests
  uv run python -m app.cli create-user <username> [--org "Company"] [--platform-admin]   # add a user / reset password
  ```
- `frontend/`: Next.js 16 (App Router, Cache Components on), Tailwind v4, shadcn/ui (`base-nova` style, built on Base UI, not Radix). Set `API_URL` in `.env.local` (see `.env.example`). Read `frontend/AGENTS.md`: this Next version differs from older ones (e.g. `middleware.ts` is now `src/proxy.ts`), and its docs are in `node_modules/next/dist/docs/`. Fonts: `layout.tsx` loads Geist into `--font-geist-sans`/`--font-geist-mono`, and `globals.css` maps `--font-sans` to them. `shadcn init` writes the self-referencing `--font-sans: var(--font-sans)`, which silently falls back to serif, so check that line after running it.
  ```bash
  npm run dev     # :3000
  npm run build
  npm run lint
  npm run gen:api   # regenerate the API client (backend server doesn't need to be running)
  npx shadcn@latest add <component>
  ```

## Organizations (multi-tenancy)

AtroNexus is a SaaS: each customer is an `Organization`, and everything a customer sets up belongs to one. `User`, `IfsConnection` and `CaptureTarget` have `organization_id`; captures belong through their target. A user is in exactly one organization and has a `role`: `owner`, `admin` or `member` and an `is_platform_admin` flag (the platform owner; the seeded admin has it and lives in the "AtroNexus" organization).

Rules for every admin endpoint, including new tools:
- Take `org_id: OrgId` (`app/deps.py`), filter every list query by it, and set it on every row you create.
- Load single rows through a helper that answers **404** when the row belongs to another organization (`_get`, `_get_target`, `get_org_connection`), never 403, so other customers' IDs can't be probed.
- A reference to another row from a request body (e.g. a target's `connection_id`) must be checked against the organization too; otherwise one customer could use another's IFS credentials.
- Endpoints that change settings or call out (save, delete, test) take `ManagerOnly` (`app/deps.py`, owners and admins); members can only read. Hide those controls for members in the frontend with `canManage()` (`src/lib/roles.ts`) or `<ManageOnly>` (`components/manage-only.tsx`); forms take `readOnly`.
- Add a cross-organization test to `tests/test_organizations.py` (the `other_org_headers` fixture signs in to a second organization).

Team (`app/team/`, frontend `/team`): owners and admins invite by email (`invitations` table, hashed one-time token, 7 days; a new invite to the same address revokes the old one; inviting needs a verified email). The public `/invite?token=` page creates the account in that organization with the invited role and a verified email. Rules in `app/team/service.py`: nobody changes or removes themselves, only owners touch owners or grant owner, an organization keeps at least one owner, and an email that already has an account can't be invited (one organization per account for now).

Tools (`app/tools/`, frontend `/tools`): `catalog.py` lists the seven tools with **placeholder** prices (monthly, plus a per-use price for tools like messaging) and whether each is built. `organization_tools` holds each organization's on/off state, and every switch is logged in `tool_events` (who and when), which billing will read later. New sign-ups start with no tools; the seeded platform organization gets every available tool; organizations from before tools existed got capture on (migration `0005`). A tool's admin endpoints take `require_tool(CODE)` (403 while off) and its public endpoints answer 404 while off. In the frontend, `getTools()` / `isToolEnabled()` (`src/lib/tools.ts`) drive the menu (`ToolAwareNav`), the home tiles, and a section layout that shows "switched off" (see `capture/layout.tsx`). A new tool needs: a catalog entry with `available=True`, `require_tool` on its routers, a public-endpoint check, a menu link with `tool:`, and a section layout.

Usage (`app/usage/`): `usage_events` gets one row per counted use, added in the same transaction as the action (`usage.record(...)`, e.g. in `capture/service.py`). A success is `billable`, a failure isn't, so customers are never charged for something that didn't reach IFS. Rows are only added, never changed; monthly numbers are sums over UTC calendar months (`usage_by_tool`). A new tool must record its own events (`"<tool>.<what>"`). `GET /api/overview` feeds the dashboard (the home page): usage this month vs last, recent errors with a link, a cost estimate for owners and admins (monthly fees of switched-on tools plus usage at the per-use price), and a setup checklist.

Platform admin (`app/platform/`, frontend `/platform`): only users with `is_platform_admin` (the seeded admin); everyone else gets **404**, so the surface doesn't reveal itself. It lists every organization with owner, members, tools, usage this month and estimated revenue (active organizations only, via `usage.cost_items`), shows one organization's members, tools, tool history and recent errors, and suspends or reactivates it with an optional reason (`status_changed_at`, `status_reason`). The platform's own organization can't be suspended. Queries here deliberately span organizations; nowhere else may.

A suspended organization (`status = "suspended"`) can't sign in (403), its tokens stop working, and its public links answer 404.

## Generated API client (Orval)

The frontend never hand-writes API calls. `npm run gen:api` runs `backend/app/export_openapi.py`, which writes `frontend/openapi.json` straight from `app.openapi()` without starting the server, and then runs Orval (`frontend/orval.config.ts`). The output goes to `src/api/generated/` (one folder per FastAPI tag plus `models/`). Don't edit it; change the backend and regenerate. Commit `openapi.json` and the generated code so API changes show up in diffs.

- **Function names come from the handler names.** `main.py` sets `generate_unique_id_function` to use `route.name`, so `def get_me` becomes `getMe()`. Handler names must be unique across the whole API.
- **Plain fetch functions, not React Query hooks.** The JWT is in an HttpOnly cookie, so only server code (server actions, server components) can call the API. `includeHttpResponseReturnType: false` makes each function return the body type directly.
- **Mutator `src/api/fetcher.ts`** (server-only): adds `API_URL`, reads the cookie and sends `Authorization: Bearer`, and throws `ApiError(status, detail)` on any non-2xx status. A 401 on a request that carried the token redirects to `/session-expired`. Calls to `/api/auth/login` and `/api/public/*` never carry the token.
- **In server actions, call `errorMessage(err)` (`src/lib/action-result.ts`) first in every catch block.** It calls `unstable_rethrow`, so the mutator's `redirect()` isn't swallowed by a catch-all.

## Auth flow

`POST /api/auth/login` (email + password; the field is called `email` but also accepts the username of accounts from before email sign-in) returns a JWT whose `sub` is the user ID and whose `iat` has sub-second precision; `GET /api/auth/me` takes `Authorization: Bearer`. A token issued before `users.password_changed_at` is rejected, so a password reset ends every other session.

Self-service: `POST /api/auth/signup` creates an organization plus its owner and signs in. Email verification and password reset use one-time links (`auth_tokens`, only a SHA-256 hash stored, a new link expires the older unused ones). Until the email is verified, `VerifiedEmail` (`app/deps.py`) blocks every endpoint that makes the server call out (save or test IFS connections and capture targets); put it on new endpoints that do. `forgot-password` answers the same whether or not the account exists. Emails go through `app/email/sender.py` as FastAPI background tasks; `EMAIL_BACKEND=console` (default) only logs them, `resend` sends through Resend. Tests read the in-memory `outbox`. `APP_URL` is the frontend address used in email links. The browser never sees the token: the login server action (`src/app/login/actions.ts`) stores it in the HttpOnly cookie `atx_session`, and server code forwards it to the API. `src/proxy.ts` only checks that the cookie exists. `/login`, `/signup` and `/forgot-password` are for signed-out users only; `/c/*` (public capture links), `/verify-email` and `/reset-password` (links from emails) are open to everyone. Signed-out pages share `components/auth-shell.tsx`; their server actions are in `src/lib/account-actions.ts`. Calls to the no-token auth endpoints are listed in the mutator's `NO_TOKEN_PREFIXES`. The real check is any API call: when the API rejects a token, the mutator redirects to `/session-expired`, which clears the cookie and goes to `/login`. That avoids a redirect loop with the proxy.

Admin pages live in the `src/app/(admin)/` route group. Its layout is a shadcn sidebar (based on the `sidebar-07` block: collapses to icons with Ctrl/Cmd+B, a drawer on phones). The menu is in `components/app-sidebar.tsx` (sections, tool links shown only while the tool is on, Customers only for the platform admin, the user menu with Sign out); `app-sidebar-loader.tsx` loads its data inside `<Suspense>` with the data-less sidebar as fallback; `app-header.tsx` is the breadcrumb. Add a new page's menu entry in `sections()` and its label in the breadcrumb maps. Light/dark mode uses `next-themes` (`components/theme-provider.tsx`, default: same as the device; the choice is in the sidebar's user menu); colours come from the `.dark` variables in `globals.css`, so use theme tokens (`bg-muted`, `text-muted-foreground`, ...) and give any hard-coded colour a `dark:` variant. Page titles go through `PageHeader` (`components/page-header.tsx`). Components from the shadcn CLI import `cn` from the npm package `cn` (shadcn's own, which `src/lib/utils.ts` re-exports); that's correct, leave it. Nothing rendered in a prerendered fallback may use `Math.random()` or the current time (Cache Components refuses it), which is why the sidebar skeleton has fixed widths instead of `SidebarMenuSkeleton`. With Cache Components on, anything that reads cookies, `params`, `searchParams` or `usePathname()` must sit inside `<Suspense>`. Pages stay synchronous and pass the `params` promise to an async child (see `capture/[id]/page.tsx`).

## IFS connector (`backend/app/ifs/`)

Every IFS call goes through `IfsClient` (`client.py`). It supports OAuth2 client credentials (IFS Cloud's default, tokens cached per connection until shortly before expiry) and basic auth. It raises `IfsError` with the message pulled from the IFS OData error body. Secrets are Fernet-encrypted (`app/crypto.py`) and never returned by the API: `IfsConnectionOut` has no secret field, and on update an empty secret keeps the saved one. Tests swap `app.ifs.client.transport` for an `httpx.MockTransport`.

**Internal addresses are blocked (SSRF guard, `app/ifs/netguard.py`).** Customers type IFS addresses, so `check_url` requires https and refuses any host that resolves to a non-public address (loopback, private, link-local incl. 169.254.169.254, CGNAT, multicast, reserved; IPv4-mapped IPv6 unwrapped). It runs when a connection is saved (422 with a readable message) and again before every request in `IfsClient` (DNS can change); the client never follows redirects. Any new code that calls a customer-supplied URL must go through it. `ALLOW_PRIVATE_IFS_URLS=true` switches it off for local development with a fake IFS; never in production. Tests replace `netguard.resolve` with a fake DNS (`fake_dns` fixture). Known gap: DNS rebinding between the check and httpx's own lookup; closing it needs connecting to the checked IP.

TLS is verified against the OS trust store (`truststore`), not certifi. Keep it that way: real IFS servers (e.g. the DSS UAT) send only their leaf certificate without the intermediate. Windows and macOS fetch the missing intermediate like browsers do, but certifi/OpenSSL fails with `unable to get local issuer certificate`. Linux doesn't fetch intermediates either, so the Docker image adds every `backend/certs/*.crt` to the system store (truststore reads it on Linux). The Sectigo intermediate for DSS UAT is there; see `backend/certs/README.md` to add others. Never turn verification off.

## Tool 1: capture page (`backend/app/capture/`, `frontend/src/app/c/`)

- A **capture target** says which connection to use, the IFS endpoint path (with `{request_id}`), PATCH or POST, and a JSON body template (`template.py`; a value that is exactly one placeholder keeps its type). Its random `public_id` goes in the link: `/c/<public_id>/<request id>`.
- For PATCH, the backend GETs the record first. A 404 means the request ID doesn't exist in IFS, so nothing is written. Otherwise it sends the ETag as `If-Match`.
- A request ID can be sent once. A failed attempt can be retried and overwrites the earlier row in `captures`. `request_id` is restricted to `[A-Za-z0-9_.:-]{1,100}` because it goes into the IFS URL.
- **Client IP:** see Deployment above. Off Vercel, a browser can set `x-real-ip`/`x-forwarded-for` itself, so another host would need a proxy that overwrites them.
- **Rate limits** (`app/ratelimit.py`, in-memory, per backend process): opening a capture link 60/min per visitor IP; submitting 10/min and 60/hour per visitor, plus 300/hour per capture page from everyone together (so a leaked link can't flood IFS). Over the limit: 429 with `Retry-After`. The visitor IP is `X-Client-IP`, which the frontend must send on every public call (`clientIpHeaders()` in `src/lib/client-ip.ts`); without it all visitors share Vercel's IP and one limit. Reuse `RateLimiter` + `enforce` for other public endpoints (sign-in, sign-up, password reset are still unlimited). With several backend instances each counts separately; exact limits would need a shared store.
- **New link** (`POST /api/capture/targets/{id}/new-link`, owners and admins): a new random `public_id`, so every old link stops working at once; the IFS custom command must then be updated. Links are still shared per capture page, not per request; per-request one-time links are planned with the secure-links building block.

This repo sits inside `C:\_PERSONAL\agrum`, whose `CLAUDE.md` is also loaded. That file describes the separate Agrum projects (`agrum_be`, `agrum_fe`, `agrum_mobile`), not AtroNexus. Its rules don't apply here unless AtroNexus decides to reuse that stack.

## Tool 3: approvals from email (`backend/app/approvals/`, `frontend/src/app/a/`, `ifs/approvals/`)

Two halves:
- **IFS package** (`ifs/approvals/`, customer builds and deploys it; see its README): `C_Atx_Approval_Util_API` + projection `CAtxApprovalHandling` (component PURCH, layer Cust, no tables), an event action on the standard event `PUR_REQ_LINE_TO_BE_AUTHORIZED`, and an IFS Connect routing rule/address. IFS signs a token per step and person with HMAC-SHA256 (secret in the object property `CAtxApproval / * / HMAC_SECRET`, which AtroNexus never sees), posts the request to AtroNexus, and on Approve/Reject checks the token, **impersonates the approver** (`Fnd_Session_Util_API.Impersonate_Fnd_User_`, needs the service user's `IMPERSONATE USER` privilege) and runs the standard `Check_Authorizer` + `Authorize__` / `Update_Rejection_Details__`. So IFS records the real approver with their own limits. The PL/SQL was written against the 25.1 core in `C:\_WORK\Core files` and hasn't been compiled here.
- **AtroNexus**: IFS posts to `/api/hooks/ifs/approvals` on the **frontend** (`src/app/api/hooks/ifs/approvals/route.ts` forwards it with the internal key) with `Authorization: Bearer <hook key>`; the key's hash identifies the organization (`ApprovalSetup`). Each approver gets an `ApprovalRequest` (IFS token stored encrypted, only passed back) and a **secure link** (`app/links/`: hashed one-time token, expiry, revocable). The public page `/a/<token>` reads the line live from IFS; deciding is a deliberate button press (opening a link never acts, because email scanners open links). A decision closes the other approvers' links for that step and counts as usage (`approvals.decided`). If IFS refuses (e.g. over the approver's limit) the link stays usable and the error is logged. Admin page `/approvals`: setup steps, hook key (shown once), connection, link lifetime, a package check, and the request log.

## What the platform is

AtroNexus is a set of seven small tools that fill gaps in IFS Cloud. Each tool connects to IFS through its REST API, and all of them follow the same round trip:

1. Something happens in IFS (a user clicks a custom command, or a custom event fires).
2. IFS calls the tool, or opens the tool's page, passing a reference to the record (for example a one-time request ID).
3. The tool does what IFS can't do by itself.
4. The tool writes the result back to IFS through the REST API, using that customer's service user.
5. IFS's own logic (validations, events, status changes) carries on from there.

| # | Tool | Gap |
| --- | --- | --- |
| 1 | Capture page | The browser client can't read location, IP address or device |
| 2 | Messaging hub | No built-in WhatsApp or SMS |
| 3 | Approve from email or chat | Approvals need a login or the Notify Me app |
| 4 | Email in, record out | An incoming email can't create a record |
| 5 | Guest links and forms | People without an IFS login can't view or submit anything |
| 6 | SharePoint/OneDrive documents | No link between IFS documents and Microsoft 365 |
| 7 | Configuration change tracker | No audit trail for configuration changes |

### Shared building blocks

Build each of these once and reuse it. Don't reimplement them inside individual tools.

| Block | Used by |
| --- | --- |
| IFS connector (REST API, one service user per customer) | All |
| Secure links (signed, expiring, one-time, tied to one person and one item) | 1, 3, 5 |
| Message channels (WhatsApp, SMS, email) | 2, 3, 4, 5, 7 |
| IFS configuration package (custom entities, commands, events) | 1, 2, 3, 5, 6 |
| Admin console and logs (per-customer settings, usage, errors) | All |

### Build order

The planned order is: capture page (it proves the IFS → tool → IFS round trip), then the messaging hub (tools 3, 4 and 5 depend on it), approvals, email-in, SharePoint, and guest links last. The change tracker needs only the IFS connector, so it can be built at any point.

## Constraints from the design doc

- **Multi-tenant credentials.** The platform holds an IFS service user for every customer. Store those credentials encrypted and keep each customer's data separate.
- **Secure links are keys.** They must expire, work once, belong to one recipient, and be revocable. A guest link exposes exactly one item, never a list or a search. High-value approvals also need a PIN or sign-in.
- **Audit.** When a tool acts through a service account, IFS must still show who really performed the action.
- **Licensing.** Tool 5 (and, to a lesser degree, tool 3) gives outsiders access to IFS data. That may count as indirect access under the IFS licence and needs written confirmation from IFS before it ships.
- **The capture page must be served over HTTPS** or browsers won't give it the location. The user can refuse access, and the location can be faked.
- **WhatsApp Business** messages that the business starts need pre-approved templates and recipient opt-in. Track message counts per customer, since every message costs money.
- **The change tracker only reads from IFS**, but its snapshots contain SQL and business logic, so they need the same protection as the system itself.
- **Gaps may be out of date.** Some evidence comes from old IFS Community threads. Re-check each gap on the target IFS release before building it.

Open questions (supported IFS releases, SMS/WhatsApp providers, single-hosted vs per-customer install, whether IFS exposes modified-by for each configuration type) are listed at the end of the design doc. Check them before you make an architecture decision that depends on one.
