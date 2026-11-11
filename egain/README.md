# eGain console blueprint for ResolveLoop

Follow the eGain AI Agent Developer Lab order exactly (Parts B, C, D). This file gives the values to type at each
step so the published agent tells the ResolveLoop story. Record what you observe in `egain/OBSERVED.md` (what the
tenant actually supports) before claiming anything in the submission.

Tenant: https://aidev.egain.cloud/y6ip (profile menu → Change consoles → AI Agent).
Hosted backend: https://srv1619809.hstgr.cloud/resolveloop (health: `/health`, desk UI: `/ui/`, help center page: `/ui/orbit.html`, PDFs: `/kb/0N-….pdf`).

## Part B — First-time AI Agent setup (Files & Websites)

- Agent name: **Orbit Support Assistant**. Language: English (US).
- Data source: Files and Websites → Upload Files → the five PDFs from `knowledge/pdf/` (or point to the website
  `https://srv1619809.hstgr.cloud/resolveloop/ui/orbit.html`, which links the same PDFs).
- Train AI Agent → wait for "Training is complete".
- Intent screen: review the generated topics. Expected topics include exporting reports, migration, roles and
  permissions, plans and subscription, getting help. Rename the export topic to **Export Troubleshooting** if the
  console allows, because the process workflow attaches to it.
- Test questions (grounded answers expected):
  - "Which roles can export reports?" → analysts and admins with the Export permission; viewers cannot.
  - "What does error EXP-200 mean?" → subscription inactive, workspace read-only.
  - "How do I know if my workspace moved to Orbit Cloud 2?" → from the migration article.
  - Knowledge-gap probe: "My export has been spinning since we migrated, how do I fix it?" → the articles say to
    contact support with the account ID; the agent must not invent a fix. This is the escalation trigger.

## Part C — Personalize & Publish

- Assistant name: Orbit Support Assistant. Keep the eGain theme.
- Extra guidance (paste into the guidance box):

  > You are the support assistant for Orbit Analytics' product Orbit Reports. Answer only from the Orbit help
  > articles. Always ask for the customer's Orbit account ID (format C001) before discussing account-specific
  > problems. If a feature worked before the Orbit Cloud 2 migration and now fails, do not guess at a fix: say
  > that a specialist needs to review the migration record and offer to connect them. Never tell a customer that
  > something has been fixed unless a verification result confirms it. Demo content is fictional.

- Embed domain: `srv1619809.hstgr.cloud` (Add Domain). Proceed → Finish Setup.
- Demo link: Personalize & Publish → Demo Link → page URL `https://srv1619809.hstgr.cloud/resolveloop/ui/orbit.html`
  → Create Demo link → Open Demo Link. Paste the resulting URL into `egain/OBSERVED.md` and the submission form.

## Part D — Workflows (Workflows tab, top left of the AI Agents dashboard)

### Pre-chat workflow — name `Orbit Prechat`

1. Start → **Question** (Select): "What do you need help with today?" Options: `Exports and downloads`,
   `Orbit Cloud 2 migration`, `Roles and permissions`, `Billing and subscription`, `Something else`.
2. Every option → **Question** (Text): "What is your Orbit account ID? (demo accounts: C001, C002, C003)".
   Variable key: pick the closest available key (lab used `userQuery`; if a custom key such as `accountId` can be
   created, use it, else keep the ID in the message text).
3. → **Question** (Text): "Briefly, what is happening?" Variable key: `userQuery`.
4. → **Send to AI Agent**. Publish → Publish Workflow.
5. Integrate: AI Agents → agent → Personalize and Publish → Pre-Chat → toggle on → select `Orbit Prechat`.

### Escalation workflow — name `Orbit Escalation`

1. Start → **Question** (Select): "A specialist can take this from here. How would you like to be contacted?"
   Options: `Email ticket`, `Phone or callback`.
2. `Email ticket` → **Send Email** (Connector Actions): To `support@orbit-analytics.example`; Subject
   `Orbit chat escalation {sessionId}` (insert the sessionId variable with the curly-brace picker); Body
   `A customer needs specialist help after the assistant could not resolve the issue. Session transcript attached
   where available.`; Escalation message: `We have opened a ticket with our specialists. You will hear back within
   one business day.`
3. `Phone or callback` → **Statement**: `You can reach a specialist by phone, or request a callback, Monday to
   Friday 8 am to 6 pm Pacific.` → **Trigger Call** (Connector Actions): Phone number `(555) 010-0199`; Escalation
   message `Here is our support line. Mention your account ID when you call.`
4. Publish → Publish Workflow.
5. Integrate: Personalize and Publish → Escalation → mode `Escalation Workflows` → Direct Escalation =
   `Orbit Escalation`; Knowledge Gap Escalation = `Orbit Escalation` (Dislike too, if offered).

### Process Tools workflow — name `Orbit Export Troubleshooter` (attach to the export intent)

1. Start → **Question** (Select): "What happens when you try to export?" Options:
   1 `The Export button spins or the download never starts`, 2 `Error EXP-100 (no export permission)`,
   3 `Error EXP-200 (subscription inactive)`, 4 `Error EXP-300 (report too large)`, 5 `Something else`.
2. Option 1 → **Question** (Select): "Did your workspace move to Orbit Cloud 2 recently?" Options `Yes`, `No`.
   - `Yes` → **Question** (Text): "Please confirm your Orbit account ID so I can check your account." then
     → **Action** node (if the tenant offers HTTP/API actions, see Actions below) calling ResolveLoop; its
     response text is shown in a **Statement** (`{resolve.message}` or equivalent field mapping).
     If actions are not available in the tenant: **Statement**: `This matches a known post-migration permission
     issue. A specialist applies an approved fix and verifies your export. I am connecting you now.` → escalate
     (Send to escalation / end node), and the human runs it from the ResolveLoop desk.
   - `No` → **Statement**: `Please sign out and back in, then retry the export from the report toolbar. If it still
     hangs, I can connect you with a specialist.`
3. Option 2 → **Statement**: `Error EXP-100 means your user is missing the Export permission. A workspace admin can
   enable it under Admin → Users → your name → Export. Viewers cannot export; ask an admin for the analyst role.`
4. Option 3 → **Statement**: `Error EXP-200 means the subscription is inactive and the workspace is read-only.
   Your billing owner can reactivate it under Admin → Billing. Exports resume within a few minutes.`
5. Option 4 → **Statement**: `Error EXP-300 means the export exceeds the limit (CSV 1,000,000 rows or 250 MB; PDF
   200 pages or 50 MB). Add a filter or a date range and try again.`
6. Option 5 → **Send to AI Agent** (or a Statement that offers a specialist).
7. Publish → Publish Workflow. Integrate: Test AI Agent tab → find the export intent → pencil → Assign Workflow →
   `Orbit Export Troubleshooter`.

### Actions (hackathon requirement 06)

Enable Actions on the agent, then add an action with these values if the tenant offers an HTTP/API action:

- Name: `ResolveLoop resolve`
- Method/URL: `POST https://srv1619809.hstgr.cloud/resolveloop/v1/resolve`
- Headers: `Content-Type: application/json`, `X-API-Key: <value from .env on the VPS>`, `X-Tenant-ID: demo`
- Body: `{"account_id": "<account id variable>", "utterance": "<customer message variable>", "confirm": true,
  "idempotency_key": "<sessionId>", "channel": "egain"}`
- Response fields to show the customer: `message` (always), `data.outcome` (`resolved` | `escalate` |
  `needs_confirmation`), `data.escalation_options` when escalating.
- Test accounts: C002 (eligible → resolved after a playbook is approved), C003 (inactive → refused),
  C013 (viewer → refused). Before any playbook is approved every account returns `NO_PLAYBOOK`.

Only the request above is supported. Do not call other endpoints from eGain. If the console offers no outbound
action, record that in `egain/OBSERVED.md` and use the Statement fallback in the process workflow (Path B).

## Validation (requirement 07)

Run each path in Test AI Agent, then again on the published demo link after up to five minutes:

1. Grounded answer: "Which roles can export reports?"
2. Pre-chat: category + account ID collected before the agent greets.
3. Knowledge gap: "My export has been spinning since we migrated" → escalation workflow with both options.
4. Direct escalation: "I want to talk to a person" → both options.
5. Process workflow: "Export is not working" → troubleshooter → option 1 → Yes → action or fallback.
6. Action (if configured): C002 after approval → resolved; C003 → refused.
Record screenshots under `evidence/egain-*.png`.
