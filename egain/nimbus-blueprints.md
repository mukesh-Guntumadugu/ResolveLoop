# Nimbus Support Assistant: second eGain agent on the same loop (telecom domain)

Everything below mirrors the Orbit agent one to one, so the console steps are the same lab steps; only the
content, the variable values and the account ids change. Base URL for every API node and action:
`https://srv1619809.hstgr.cloud/resolveloop`, headers `X-Tenant-ID: demo`, `X-API-Key: <demo key>`.
Telecom line ids are `N001..N012`; the backend infers the domain from the `N` prefix, so no extra header is needed.

## 1. Agent (Point to Content → Train)

- Name: **Nimbus Support Assistant**. Language: English.
- Files (public bucket only, from `knowledge/telecom/pdf/`): 01-using-your-phone-abroad, 02-core-network-upgrade-5,
  03-plans-and-add-ons, 04-line-status-and-suspensions, 05-getting-help.
- Expected intents after training: roaming and data abroad; Core Network Upgrade 5; plans and add-ons; line status and
  suspensions; getting help / escalation.

## 2. Personalize and Publish

- Display name "Nimbus Support Assistant", teal theme, static greeting:
  "Hi, I'm the Nimbus Support Assistant. I can answer questions about your plan, roaming and the Core Network Upgrade,
  check your line, and apply approved fixes. What can I help with?"
- Disclaimer: fictional carrier for the eGain AI Agent hackathon; demo lines N001..N012; no real customer data.
- Default escalation contacts: support@nimbus-mobile.example, (555) 010-0288.
- Additional instructions: ask for the line id (N###) before checking anything; never promise credits or refunds, hand
  those to a specialist; cite the article you used.

## 3. Pre-chat workflow "Nimbus Prechat"

Start → Question(Select → `issueCategory`: Roaming or data abroad / Core Network Upgrade 5 / Plan, add-ons or billing /
Something else) → Question(Text → `accountId`, "What is your Nimbus line ID? (Demo lines: N001, N002, N003)") →
Question(Text → `userQuery`, "Briefly, what is happening?") → Send to AI Agent (userQuery, accountId, issueCategory).
Leave the Invalid handle of the last question unconnected (publish check).

## 4. Escalation workflow "Nimbus Escalation" (Direct, Knowledge Gap, Dislike)

Start → Question(Select: Email ticket / Phone or callback)
- Email ticket → API POST `/v1/tickets` body `{"account_id":"{{accountId}}","category":"{{issueCategory}}","summary":"Escalation from chat: {{userQuery}}","session_id":"{{sessionId}}"}` → `data.number` → `ticketNumber` → Send Email (to support@nimbus-mobile.example, subject `[{{ticketNumber}}] Nimbus escalation for {{accountId}}`, include chat history) → Statement quoting the ticket.
- Phone or callback → Statement (hours Mon–Sat 8am–8pm) → Phone input → `callbackPhone` → API POST `/v1/callbacks` body `{"account_id":"{{accountId}}","phone":"{{callbackPhone}}"}` → `data.number` → `callbackNumber` → Statement → Trigger Call (555) 010-0288. On Error / On Timeout → Trigger Call.
- Header `X-Tenant-ID` value must be exactly `demo` (a pasted JSON body once got appended to it).

## 5. Process workflow "Nimbus Roaming Fix" (assign to the roaming intent)

Start → Question(Select → `symptom`: No data abroad or RM-100 / RM-200 plan has no roaming / RM-300 line suspended /
Something else)
- RM-100 / no data → Question(Yes/No: "Was your line part of Core Network Upgrade 5?") → Yes → Question(Text confirm
  `accountId`) → Question(Yes/No consent: "May I re-enable roaming on this line?") → Yes → **API GET**
  `/v1/resolve?account_id={{accountId}}&utterance=no data abroad RM-100 after CNU-5&confirm=true&channel=egain-workflow`
  → map `message` → `resolveMessage`, `data.outcome` → `resolveOutcome` → Statement `{{resolveMessage}}`.
  No consent → Statement (how to reach a specialist). No (not upgraded) → Statement (check add-on, restart, contact).
- RM-200 → Statement (add the roaming add-on under Plan in the app; Go plan needs the add-on).
- RM-300 → Statement (line suspended: Billing > Reactivate; a specialist can help) → nothing automated (restricted).
- Something else / Invalid → Question(Text → `userQuery`) → Send to AI Agent.
- On Error / On Timeout of the API node → Statement with the two contact options.

## 6. Process workflow "Nimbus Line Check" (assign to the plans / line status intent)

Start → Question(Text → `accountId`) → API GET `/v1/accounts/{{accountId}}/status` → map `data.active` → `accountActive`,
`data.summary` → `accountSummary`, `data.plan` → `accountPlan` → Condition (`accountActive` Equals "true") → Statement
(active: summary) / Else Statement (suspended RM-300: reactivate under Billing or talk to a specialist) → Question(Text →
`userQuery`) → Send to AI Agent (userQuery, accountId, accountSummary). Invalid / On Error / On Timeout → error Statement.

## 7. Actions (Enable Actions → Custom APIs)

1. **ResolveLoop fix roaming** – POST `/v1/resolve` body `{"account_id":"{{account_id}}","utterance":"{{utterance}}","confirm":"{{confirm}}","channel":"egain"}`; description: "Apply the reviewer-approved fix for a Nimbus line that lost roaming after Core Network Upgrade 5. Ask the customer for permission first and send confirm=true only after they agree."
2. **Check Nimbus line status** – GET `/v1/accounts/{{account_id}}/status`; description: "Live status of a Nimbus line: active, plan, roaming enabled, and what is wrong (RM-100/200/300)."
3. **Open a Nimbus support ticket** – POST `/v1/tickets` body `{"account_id":"{{account_id}}","category":"{{category}}","summary":"{{summary}}"}`.

## 8. Validation checklist (Test AI Agent, then the published link, after ~5 min propagation)

- Grounded answer: "Which plans include roaming?" cites 03-plans-and-add-ons.
- Pre-chat → Roaming → N001 → "No data since I landed in Spain, RM-100" → Nimbus Roaming Fix → consent → resolved.
- N003 (suspended) same message → refused, RM-300, escalation options.
- "I want to speak to an agent" → ticket number quoted; callback branch → CB number.
- Free text after Something else → agent picks the line-status action on its own.
- Record every result in `egain/OBSERVED.md` with a screenshot under `evidence/`.
