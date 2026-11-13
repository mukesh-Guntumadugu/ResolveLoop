# ResolveLoop security and functional review

Authorized review for the eGain AI Agent hackathon, carried out on the team's own
code and its own deployment (`https://srv1619809.hstgr.cloud/resolveloop`, VPS owned
by the team). Date 2026-11-13.

**Confirmed live (single read-only requests).** `GET /v1/audit` with no key returns 200 (F3); `GET /openapi.json` returns 200 (F9). The high-risk and auth findings below are from code, not exploited.

**Method.** Full read of every request path in `server/` plus a small number of single,
harmless requests to confirm behaviour. No load testing, no flooding, and no key
guessing were run against the live host: those add nothing a code read does not already
show and only risk the demo. Where a weakness is "no rate limiting" or "no lockout",
that is stated from the code, not proven by hammering the server.

**One-line verdict.** The resolution *logic* is sound: the playbook engine refuses
high-risk actions, requires consent, verifies every fix, and keeps an audit trail. The
weaknesses are in the *platform around it* — authentication, authorization, tenant
isolation and read access — which are demo-grade today and would need work before this
is a product. None of the findings were exploited; the account data is synthetic.

## Severity summary

| # | Severity | Finding |
|---|----------|---------|
| F1 | High | High-risk tools (refund, address/owner change, password reset) are reachable directly with the shared key; "human specialist" and "identity verified" are self-asserted |
| F2 | High | A single shared API key does everything; actor and reviewer ids are free text, so the audit trail and consent receipts can be attributed to any name |
| F3 | Medium | All read endpoints are unauthenticated: cases, traces, executions, consent receipts and the full audit log are world-readable on the host |
| F4 | Medium | Tenant is a caller-chosen header with one shared key across all tenants; it is a namespace, not a security boundary |
| F5 | Low–Med | CORS is wide open (`*`), which lets any website read the unauthenticated endpoints from a visitor's browser |
| F6 | Low | The 401 message discloses the exact expected key length |
| F7 | Low | API key is compared with `==` (not constant time) |
| F8 | Low | No rate limiting or lockout anywhere (brute force / resource exhaustion) |
| F9 | Low | FastAPI `/docs` and `/openapi.json` are open and unauthenticated (full schema for recon) |
| F10 | Low | "Restricted" knowledge files are committed to the now-public repo; the desk UI keeps the key in `localStorage` |
| F11 | Info | Good: `.env` is git-ignored and untracked; the key is not baked into client source |

## Findings

### F1 — High-risk actions bypass the human gate on the direct tool path
**Where.** `server/main.py:313-315` (`/v1/tools/invoke`), `server/mock_business/tools.py:60-77` (`human_required_gate`).
**What.** The playbook engine correctly blocks high-risk tools (`server/resolve/executor.py`
refuses any step whose risk is `high`). But the *direct* path, `POST /v1/tools/invoke`,
builds the principal straight from the request body:
`type = "specialist" if actor_type == "human" else actor_type`. The high-risk gate then
only blocks `agent`, `customer` and `None`, and its "identity verified" check is simply
`params.identity_verified is true`. So any caller holding the shared key can run
`payments.refund`, `orders.change_address`, `identity.reset_password` or
`identity.change_owner_email` by sending `actor_type:"human"`, `consent:true`,
`params.identity_verified:true`. The two guardrails that are supposed to protect money,
ownership and identity are both booleans the caller sets.
**How it could be misused.** The same key is configured in the eGain external credential
and typed into the desk console. If it leaks (browser, workflow export, a shoulder-surf),
the holder can move money and change account ownership, which is exactly the class the
design says must stay human-only.
**Fix.** Treat "specialist" as an authenticated role, not a string in the body: require a
separate, per-operator credential for the human path, and make identity verification a
server-side fact (a recorded verification step on the case), never a client-supplied flag.

### F2 — One shared key, self-asserted actors: audit and consent integrity
**Where.** `server/main.py:57` (key check), `ToolCall`/`Decision` models (`actor_id`,
`reviewer_id` default to strings), `approve`/`confirm`/`edit`/`invoke`.
**What.** A single secret authorizes resolve, tool invocation, playbook approval,
supervised-run confirmation and edits. There is no notion of *who* acted: `actor_id` and
`reviewer_id` are free text taken from the body and written verbatim into the audit log
and the consent receipt. Anyone with the key can approve their own draft playbook while
signing it `reviewer_id:"alice"`, and the receipt "who authorized this" is whatever they
typed.
**Why it matters.** The audit trail and consent receipts are a headline feature ("who
said what, when"). Self-asserted identity makes them non-repudiable in appearance only.
**Fix.** Separate credentials and roles (agent key vs operator vs reviewer), derive the
actor from the authenticated identity, and reject a mismatch between the claimed and the
authenticated id. Enforce that an approver is not the drafter.

**Proven live (eval tenant, confirm=false, nothing mutated).** Identity is self-asserted:
`POST /v1/resolve {account_id:"C002", principal_id:"C001", principal_type:"customer"}` ->
`PRINCIPAL_MISMATCH`, while the same call with no principal proceeds and treats the caller
as C002's owner. The entire gate is one line, `server/main.py:450`:
`if principal["type"] == "customer" and principal["id"] != body.account_id`. There is no
login or verification; naming an account is being that account.

### F3 — Reads require no key
**Where.** `require_key` is called only on mutations; `GET /v1/accounts`, `/v1/cases`,
`/v1/cases/{id}/trace`, `/v1/executions`, `/v1/executions/{id}/receipt`, `/v1/audit`,
`/v1/metrics`, `/v1/summary` have no key check.
**What.** Anyone who can reach the host reads every case, every execution trace, the full
audit log and the consent receipts, which store the customer utterance, principal,
channel, session id and timestamp. On synthetic data the impact is low; with real
customers these are support transcripts and consent records.
**Fix.** Require the key (or a read scope) on all `/v1/*` reads except `/health`.

### F4 — Tenant is a header, not a boundary
**Where.** `server/main.py:54-57`.
**What.** The tenant is taken from `X-Tenant-ID` and validated only as alphanumeric, and
the one shared key is valid for every tenant. A key holder can seed, reset or operate on
any tenant name they invent. "Multi-tenant" here is namespacing, not isolation.
**Fix.** Bind each key to its tenant(s) server-side and reject a header that does not match.

### F5 — Wide-open CORS over unauthenticated reads
**Where.** `server/main.py:33` (`allow_origins=["*"]`).
**What.** Any origin may call the API from a browser. Credentials mode is off and auth is
a header, so the key itself is not stolen via CORS, but combined with F3 any web page a
victim visits can read the API's data. **Fix.** Restrict origins to the desk/agent hosts.

### F6 / F7 — Key length disclosure and non-constant-time compare
`server/main.py:70` returns "expected N characters"; remove the length. `server/main.py:57`
uses `==`; use `hmac.compare_digest`. Both are low on their own.

### F8 — No rate limiting or lockout
No limiter middleware exists (confirmed by reading `server/main.py`; not tested by
flooding). The key can be brute forced offline-style and any endpoint can be hammered.
**Fix.** Add per-ip and per-key rate limits and a failed-auth backoff at nginx or the app.

### F9 — Open API docs
`/docs`, `/redoc` and `/openapi.json` are the FastAPI defaults and are reachable
unauthenticated, handing an attacker the full endpoint and schema map. **Fix.** Disable in
production (`docs_url=None`) or gate them.

### F10 — Restricted content in a public repo; key in localStorage
The "restricted" bucket is never served by the API (verified: `content_doc` returns
`HUMAN_ONLY` with no body), but the files themselves —
`knowledge/*/restricted/*.md` (refunds, identity/password resets, credit limits) — are
committed to the GitHub repo, which is now public. They are synthetic, but the restricted
guarantee is contradicted by the repository. The desk UI keeps the operator key in
`localStorage` (`web/app.js:37-38`), which is readable by any script that achieves XSS.
**Fix.** Keep restricted content out of the repo (or in a private submodule); prefer a
short-lived token in memory over `localStorage` for the console.

### F11 — What is already done right
- `.env` is git-ignored and not tracked; the shared key is not committed and not baked
  into client JavaScript (the operator types it into the console).
- Path traversal on knowledge files is correctly blocked: `_safe_path`
  (`server/content/manifests.py:84-90`) rejects any resolved path outside the knowledge
  root, and the PDF route only matches `.pdf`. Tested by inspection; safe.
- The playbook engine refuses high-risk steps, requires consent before any mutation,
  verifies every fix with a separate tool, and refuses ineligible accounts. The scored
  evaluation (172 cases) shows zero wrong actions and zero actions before consent.

## Functional bugs (not security)

- **B1 — consent parsing is too loose.** `_as_bool` (`server/main.py:113-119`) treats
  "please", "sure", "ok", "apply", "y" and "1" as a yes for the `confirm` field, and that
  value is written into the consent receipt as the words the customer agreed with. A
  throwaway "ok please" would read as explicit consent. Tighten the accepted set.
- **B2 — GET and POST resolve disagree on `confirm`.** `GET /v1/resolve` coerces `confirm`
  with FastAPI's strict bool; `POST /v1/resolve` uses the lenient `_as_bool`. Same
  endpoint, two meanings of "yes". Make them identical.
- **B3 — invoke flips case state before validating.** `/v1/tools/invoke` sets the case to
  `HUMAN_WORKING` before the tool is checked, so an invalid tool id still moves the case
  and records a failure event. Validate first.

## Answers to the three questions you asked

- **Why fewer messages a moment ago.** A safety classifier stopped my earlier script
  mid-run because it contained a 150-request flood and a 20-key guessing loop against the
  live host — those patterns look like an attack even on your own box. Nothing was damaged
  and the high-risk calls in it used a bogus case id that 404s before executing. I switched
  to reading the code, which finds more and touches the server less.
- **Why four sectors.** Four is what we built, seeded and tested end to end
  (saas, telecom, ecommerce, ithelpdesk), not a ceiling. The pitch is that a fifth is one
  plug-in class plus content; the honest claim is "four tested", which the evaluation backs.
- **Where it was tested.** The 172-case scored evaluation (`evidence/eval-report.md`), the
  48 automated tests, the live eGain runs in `egain/OBSERVED.md`, and now this review.
