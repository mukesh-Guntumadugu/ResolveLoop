# What was actually observed in the hackathon tenant

Fill in while building; the submission must only claim what is recorded here.

| Capability | Observed? | Notes / screenshot |
|-----------|-----------|--------------------|
| Trial tenant sign-in (AI Agent console) | yes | Profile menu → Consoles → **Agentic Studio** ("AI Agent for Customer"); "AI Console" is AssistGPT prompt templates, not the agent builder. Tabs: AI Agents, Workflows, External Credentials. |
| Train on 5 uploaded PDFs | yes | Setup wizard: Point to Content → Files and Website → Files. Accepts .html/.pdf/.docx, up to 10 files, 5 MB each. 5 PDFs = 26,909 chars; "Train AI Agent" started 2026-11-11. |
| Generated intents include an export topic | yes | 5 intents generated: Export Configuration and Troubleshooting; Subscription and Billing Management; User Roles and Access Control; Platform Migration and Updates; Technical Support and Escalation. Test chat: "Which roles can export reports?" → grounded answer citing 03 and 01 PDFs. Probe "export spinning since we migrated" → says contact Orbit Support with account ID, no invented fix (cites 02, 01). |
| Published demo link works | created | Demo link: https://aidev.egain.cloud/y6ip/system/web/apps/aiagent/demo.html?agentId=8ba71b10-c3ee-4a3f-b507-8fe3a4d5113a&backgroundUrl=https://cdn.aiagent-dev.egain.cloud/TMDEVEB12725755/screenshots/23a971cf-91ed-4c2b-90dc-2c54439ea014.png (background = screenshot of orbit.html). Default escalation phone +1 555 010 0199, email support@orbit-analytics.example set; cannot-answer message customised; 521-char guidance in Additional instructions. |
| Pre-chat workflow attached | **attached** (Personalize and Publish → Pre-Chat toggle → Orbit Prechat, saved) | Workflows → Pre-chat → "Orbit Prechat" v1 published 2026-11-11: Start → Question(Select: Exports and downloads / Orbit Cloud 2 migration / Billing, roles or permissions / Something else → issueCategory) → Question(Text: account ID → accountId, custom variable) → Question(Text: "Briefly, what is happening?" → userQuery) → Send to AI Agent (sends userQuery + accountId + issueCategory). Publish check: an Invalid path must not reach Send to AI Agent before userQuery is set. Blocks are drag-and-drop; edges by dragging handle to handle. |
| Escalation workflow: Direct + Knowledge Gap, two options | **attached** (Escalation mode = Escalation Workflows; Direct, Knowledge Gap and Dislike all = Orbit Escalation, saved) | Workflows → Escalation → "Orbit Escalation": Start → Question(Select: Email ticket / Phone or callback) → Email: Send Email (to support@orbit-analytics.example, subject with {{sessionId}} and {{accountId}}, body with accountId/issueCategory/userQuery, Include Chat History on, escalation message) ; Phone/Invalid: Statement → Trigger Call (555) 010-0199. Connector actions available: Chat Transfer, Send Email, Trigger Call. |
| Process workflow attached to the export intent | **attached** (Test AI Agent → Export Configuration and Troubleshooting → pencil → Assign Workflow = Orbit Export Troubleshooter) | Workflows → Process → "Orbit Export Troubleshooter" (12 nodes): Start → Question(Select: 5 symptoms) → spins: Question(migrated Yes/No) → Yes: Question(confirm accountId) → Question(consent) → Yes: **API node** GET https://srv1619809.hstgr.cloud/resolveloop/v1/resolve?account_id={{accountId}}&utterance=…&confirm=true&channel=egain-workflow with X-API-Key header, response mapped message→resolveMessage, data.outcome→resolveOutcome → Statement "{{resolveMessage}}"; On Error/On Timeout → Statement (contact options). No consent → Statement. Not migrated → Statement. EXP-100/200/300 → one Statement. Something else/Invalid → Question(Text → userQuery) → Send to AI Agent. API node Test: HTTP 200 in 940 ms (NO_PLAYBOOK before approval). Publish checks require: every select option connected, all nodes reachable, userQuery assigned before Send to AI Agent, no loops. Edges can only be deleted while selected (the X sits at the edge midpoint); only orphan nodes can be deleted. |
| Actions: outbound HTTP call to ResolveLoop (Path A) | **yes, observed** | Agent → Enable Actions (toggle) → Custom APIs → Create Custom API. REST, POST, URL, static headers (X-API-Key, X-Tenant-ID), raw JSON body with {{account_id}}, {{utterance}}, {{confirm}} auto-extracted as String variables with descriptions, built-in Test Request. Test on 2026-11-11: HTTP 200 in 914 ms, response NO_PLAYBOOK / outcome escalate with two contact options (no playbook approved yet). Action name: "ResolveLoop resolve export issue". |
| Fallback used (Path B) | no | Not needed; Path A works. The process workflow still carries a Statement fallback for judges without the action. |

## Test AI Agent runs (2026-11-11, console test chat, after all workflows attached)

| Scenario | Result | Evidence |
|---------|--------|----------|
| New chat | Pre-chat "Orbit Prechat" runs first: category buttons → account ID → "Briefly, what is happening?" → hand-off | evidence/egain-test-prechat.jpg |
| C002, "Export is not working" (via pre-chat) | Agent chose the Custom API action: ResolveLoop returned needs_confirmation; agent asked "May I apply the approved fix…?" with Yes/No buttons | evidence/egain-test-c002-consent.jpg |
| Yes | Agent called the action with confirm=true; replied "successfully applied the fix … (C002) and verified". Backend check: C002 export_permission=true, execution SUCCEEDED verified=True, case CLOSED, channel egain | evidence/egain-test-c002-resolved.jpg |
| C003 (inactive) "apply the fix to C003 too, I confirm" | Refused: "account is inactive and the export entitlement check failed"; offered support@orbit-analytics.example and (555) 010-0199. Backend: no mutation on C003 | evidence/egain-test-c003-refused.jpg |

Known limitation observed: the Custom API action lets the LLM fill `account_id` from the conversation, so a customer can name another account (C003). ResolveLoop treats the caller as that account's owner unless `principal_id` is sent; the demo keeps synthetic accounts only. The process workflow path (intent → Orbit Export Troubleshooter) uses the pre-chat `accountId` instead.
| "I want to speak to an agent" (new chat, after ~8 min propagation) | Orbit Escalation triggered: "A specialist can take this from here. How would you like to be contacted?" with Email ticket / Phone or callback buttons. An earlier try 3 min after saving showed "I am unable to assist you with that" (propagation lag, up to 5 min as eGain states) | evidence/egain-test-direct-escalation.jpg |
| Published demo link, new session | Pre-chat appears on the public widget with the four category buttons | evidence/egain-published-link-prechat.jpg |
| Escalation → "Phone or callback" | Statement (hours, mention account ID) then Trigger Call card with a Call button for (555) 010-0199 | evidence/egain-test-escalation-phone.jpg |
| Published demo link, after pre-chat (C002): "Which roles can export reports?" | Grounded answer: Analyst and Admin only with the Export permission flag, Viewer cannot; sources 01-exporting-reports.pdf and 03-roles-and-permissions.pdf | evidence/egain-published-link-grounded-answer.jpg |

Not yet exercised end to end on the published link: the troubleshooter process workflow path (intent → Orbit Export Troubleshooter → API node). The same API node passed its in-editor Test Request, and the Custom API action path resolved C002 in the console test chat.

## Upgrade round (2026-11-11 evening)

| Item | Observed |
|------|----------|
| Custom API "Check Orbit account status" | GET …/v1/accounts/{{account_id}}/status with a path parameter (auto-extracted, described). Test: HTTP 200 in 917 ms, C003 → "Subscription inactive… (EXP-200)". |
| Custom API "Open an Orbit support ticket" | POST …/v1/tickets, body variables account_id, category, summary. Test: HTTP 200 in 552 ms, "Ticket RL-1001 opened. A specialist will reply within 24 hours." |
| Escalation workflow v2/v3 (ticket + callback branches) | "Orbit Escalation" now: Email ticket → **API node** POST …/v1/tickets (body accountId, issueCategory, userQuery, sessionId; response data.number → ticketNumber) → Send Email (subject "[{{ticketNumber}}] …", escalation message quotes the ticket). Phone or callback → Statement → **Phone input** (callbackPhone) → API node POST …/v1/callbacks (data.number → callbackNumber) → Statement → Trigger Call; API errors fall through to Trigger Call. v3 fix: the X-Tenant-ID header of the callback node had the JSON body appended to its value (400 BAD_TENANT on the server), set to the literal tenant. |
| Look & Feel (Personalize and Publish) | Blue widget theme, Orbit avatar PNG uploaded for the launcher and profile picture (file inputs accept image/*), 244-char chat disclaimer, Orbit greeting as the static initial message. Persisted after reload. evidence/egain-look-and-feel-orbit.jpg |
| Process workflow "Orbit Subscription Check" | Published v1 (9 nodes) and assigned to the intent **Subscription and Billing Management**. Start → Question(Text → accountId) → API GET …/v1/accounts/{{accountId}}/status (headers X-Tenant-ID, X-API-Key; mappings data.active → accountActive, data.summary → accountSummary, data.plan → accountPlan; in-editor Test C003 → 200 in 895 ms) → Condition (accountActive equals "true") → Statement (active plan) / Else Statement (inactive, EXP-200, reactivate) → Question(Text → userQuery) → Send to AI Agent (passes accountId, accountSummary). Invalid / On Error / On Timeout → error Statement. Custom variables added: accountActive, accountSummary, accountPlan. The Invalid handle of the final question must stay unconnected (publish check). |

## Test AI Agent runs, upgrade round (2026-11-11, console test chat)

| Scenario | Result | Evidence |
|---------|--------|----------|
| Pre-chat Billing → C003 → "My subscription shows inactive, is my plan still active?" (3 min after assigning the workflow) | Agent used the **Check Orbit account status** Custom API action: "Based on the system records, your Team plan subscription is currently inactive… workspace is read-only and exports are disabled." | evidence/egain-test-c003-account-status-action.jpg |
| Pre-chat Billing → C012 → "I need to reactivate my subscription, billing says it lapsed" (8 min after assigning) | Intent routed into **Orbit Subscription Check**: asked for the account, called the API, Condition took the Else branch, replied with the live summary (Team plan, inactive, EXP-200, reactivate under Settings > Billing), then "Is there anything else I can help with…" | evidence/egain-test-c012-subscription-workflow.jpg |
| "I want to speak to an agent" → Email ticket | "Your ticket RL-1002 is open with our specialists…". Backend: GET /v1/tickets/RL-1002 → OPEN, account C012, channel egain-escalation, summary "Escalation from chat: I want to speak to an agent" | evidence/egain-test-escalation-ticket-rl1002.jpg |
| "I want to speak to an agent" → Phone or callback → "+1 555 010 2233" (escalation v2) | Hours statement, phone question, then straight to the Trigger Call card: the callback POST returned 400 (malformed tenant header, see above), so On Error → Trigger Call behaved as designed. Fixed in v3. | — |
| Same path with escalation v3, "+15550102233" | "Done. Callback CB-1003 is scheduled for the next available slot…" then the Trigger Call card. Backend: GET /v1/callbacks lists CB-1003, account C001, phone stored masked, SCHEDULED | evidence/egain-test-escalation-callback-cb1003.jpg |

## Published demo link, end to end (2026-11-12, public widget, no console)

| Scenario | Result | Evidence |
|---------|--------|----------|
| Pre-chat Billing → C012 → "I need to reactivate my subscription, billing says it lapsed" | Intent routed into **Orbit Subscription Check**: asked which account, API node called ResolveLoop, Condition took the inactive branch (Team plan, EXP-200, reactivate under Settings > Billing) | evidence/egain-published-link-subscription-c012.jpg |
| "I want to speak to an agent" → Email ticket | Escalation workflow: two options, then "Your ticket RL-1003 is open". Backend: GET /v1/tickets/RL-1003 → OPEN, account C012 | evidence/egain-published-link-ticket-rl1003.jpg |
| Pre-chat Exports → C002 → "Export is not working" | **Orbit Export Troubleshooter** process workflow: symptom buttons (EXP-100/200/300, spins, other) | evidence/egain-published-link-export-troubleshooter.jpg |
| Free text (after "Something else"): "can you check my account and fix it?" | Agent chose the **Check Orbit account status** action by itself and reported the live state (C002 already fixed on 11 Nov) | — |
| After `POST /v1/admin/reset?keep_playbooks=true` (C002 export OFF again): pre-chat Something else → C002 → "I can't download the CSV since we migrated to Cloud 2. Can you fix my account?" | Agent chose the **ResolveLoop resolve export issue** action and applied the approved playbook: "export permission has been re-enabled and verified". Backend: C002 export_permission=true, execution exe_74e105c439 SUCCEEDED | evidence/egain-published-link-action-resolved-c002.jpg |

All six requirement areas (knowledge answers, published experience, pre-chat, escalation, process workflows, actions) are now observed on the published link as well as in Test AI Agent.

## Multi-domain round (2026-11-12 night, branch multi-domain, deployed to the VPS)

| Item | Observed |
|------|----------|
| Domain registry | `GET /v1/domains`: saas (Orbit Reports, 5 tools, 5 public / 1 internal / 1 restricted docs) and telecom (Nimbus Mobile, 7 tools, 5 / 2 / 1). Reset seeds 28 accounts (16 C-accounts, 12 N-lines). Orbit endpoints unchanged (C002 status identical). |
| Content buckets | `/v1/content` serves manifest entries per bucket; restricted bodies never returned; internal bodies need the API key; telecom PDFs at `/kb/telecom/*.pdf`; desk Content tab shows the three columns with owner, approver, date, version (evidence/ui3-content-buckets.jpg). |
| Local LLM | Qwen3-8B via Ollama: GX10 (NVIDIA GB10) reached through a reverse SSH tunnel at 127.0.0.1:11435 (42.8 tok/s), VPS CPU copy at 11434 as fallback (18.1 tok/s). `GET /v1/llm/health` reports both, active = GX10, 378 ms probe. |
| LLM-drafted playbook | Case for N001 ("No data since I landed in Spain, the app says RM-100 after the network upgrade") → `POST /v1/cases/{id}/draft` → 24 s → `LLM_DRAFT` pb_bdaf4232f7, origin llm_draft, model qwen3:8b, runbooks telecom-rb-t1 + rb-t2, risk low; prerequisites: active, entitlement roaming, upgraded, roaming_enabled false; one step `lines.enable_roaming`; verifier `network.test_roaming`. |
| Supervised runs → approval | Reviewer approve → `SUPERVISED`. Paraphrase "my phone has no data abroad since the upgrade, RM-100": N002 CONFIRM_REQUIRED → RESOLVED verified (supervised), reviewer confirm 1/3; N001 resolved, 2/3; N008 resolved, confirm → `PROMOTED`, playbook `APPROVED` 3/3. N006 and N007 (not upgraded) → PRECONDITION_FAILED, escalate; N003 (suspended) and N004 (Go, no add-on) → escalate. Desk Reviewer shows the LLM-draft badge and status (evidence/ui3-reviewer-llm-draft-approved.jpg). |
| High-risk gate | `billing.issue_credit` and `account.change_owner` are risk high: playbooks cannot include them (validator), agents/customers get 403 HUMAN_REQUIRED, specialists need consent + identity_verified (7 tests). |
| Metrics | `by_domain` counters, `llm_drafts`, `supervised_playbooks`, `human_required_blocks`; dashboard tiles and LLM chip (evidence/ui3-dashboard-llm.jpg). 43 tests pass (evidence/junit.xml). |

## Second domain: Nimbus Support Assistant (telecom), 2026-11-12 night

| Capability | Observed |
|-----------|----------|
| Agent | "Nimbus Support Assistant" (id 5eb0186a-5753-4b6f-989a-e2bc98cb9cf9). Content: the five Nimbus PDFs imported as URLs from /kb/telecom/ (eGain "Enter list of URLs", 20,098 chars). 6 intents generated. Test chat: "Which plans include roaming, and what does RM-200 mean?" → grounded answer with two sources (evidence/egain-nimbus-intents.jpg). |
| Published experience | Teal theme, avatar, disclaimer, greeting, additional instructions; demo link https://aidev.egain.cloud/y6ip/system/web/apps/aiagent/demo.html?agentId=5eb0186a-5753-4b6f-989a-e2bc98cb9cf9 . |
| External credential | "ResolveLoop demo API key" (API Key, header X-API-Key), referenced by two actions and two workflows. A 401 message now says whether the key was missing or invalid and reports received vs expected length (value never echoed); the first paste was 14 characters. |
| Actions | Check Nimbus line status (GET …/accounts/{{account_id}}/status, test 200), ResolveLoop fix roaming (POST …/resolve, test 200 ALREADY_RESOLVED on an already-fixed line), Open a Nimbus support ticket (POST …/tickets, test 200 RL-1001). |
| Pre-chat | "Nimbus Prechat" published v1 and attached: category → line ID → problem → Send to AI Agent (evidence/egain-nimbus-published-prechat.jpg). |
| Escalation | "Nimbus Escalation" published v1, attached to Direct, Knowledge Gap and Dislike: Email ticket → API node POST /v1/tickets (ticketNumber) → statement; Phone or callback → hours → Phone input → API node POST /v1/callbacks (callbackNumber) → statement; all errors → contacts statement. Published link: "I want to speak to an agent" → two options; callback branch with +15550102233 → "Callback CB-1001 is scheduled" (evidence/egain-nimbus-published-escalation.jpg, -callback-cb1001.jpg). |
| Process workflow | "Nimbus Roaming Fix" published v1, assigned to intent Roaming Configuration and Troubleshooting: symptom select → consent select → API GET /v1/resolve (confirm=true) with message/data.outcome mappings → statements; RM-200 / RM-300 statements; Something else → userQuery → Send to AI Agent. |
| Agent resolving by itself (published link) | Pre-chat Roaming → N001 → "No data since I landed in Spain, the app says RM-100": the agent called the line-status action, then the fix action with confirm=false, and asked permission (evidence/egain-nimbus-published-consent-n001.jpg). The first confirmation ("Yes, please apply the fix") was re-matched by the server as a new utterance and fell back to a ticket; fixed the same night: a confirm=true call now resumes the account's pending authorized proposal (test added). Re-run on N002: consent buttons, then "Your roaming has been restored and verified as active" with sources; backend N002 roaming_enabled=true, execution SUCCEEDED (evidence/egain-nimbus-published-consent-n002.jpg, -resolved-n002.jpg). |
| Instructions hardening | After the agent once quoted a made-up phone number, the additional instructions now list the only contact details it may give and the exact confirm=false → ask → confirm=true action sequence. |

## Four sectors on one loop, and measured capacity (2026-11-12 late)

| Item | Observed |
|------|----------|
| Domain registry | `GET /v1/domains` now lists saas (Orbit Analytics), telecom (Nimbus Mobile), ecommerce (Harbor Goods: orders stuck after the WMS 4 cutover, SH-100/200/300) and ithelpdesk (Northgate University IT: VPN access lost after the SSO 2 cutover, AC-100/200/300). Reset seeds 52 accounts. 48 automated tests, including an end-to-end learning loop per sector. Live eGain agents exist for saas and telecom; the other two are backend-only sectors with content packs. |
| API capacity (VPS, one uvicorn worker, SQLite) | 50 concurrent status reads p95 0.53 s; 40 concurrent `POST /v1/resolve` p95 0.67 s; 25 concurrent ticket creations all 200. One 60 s outlier in the first 25-way run, not reproduced in three later runs. |
| LLM drafting capacity | GX10 (Qwen3-8B via Ollama, 3 slots, 16k context): 3 parallel drafts in 48 s wall, 31–48 s each, no JSON failures. With 8 slots the per-slot context shrank and drafts slowed to 77 s and failed JSON parsing twice; reverted to 3. VPS CPU fallback: 18 tok/s. nginx read timeout raised to 240 s. |
| Operational threshold | 25 concurrent agent sessions per backend instance and 3 parallel drafts, both configuration (more uvicorn workers + Postgres; more Ollama slots or vLLM). |

## Scored evaluation (2026-11-13)

| Item | Observed |
|------|----------|
| Set | `eval/sectors.py`: 156 intent-labelled cases, 39 per sector (paraphrases, already fixed, ineligible, broken verifier, out of scope, vague, injection, cross-sector). Runner `python -m eval.run_eval`; gate `tests/test_eval_gates.py`. |
| Live run (VPS, tenant `eval`) | accuracy 97.4%; match precision 100%; recall 95%; eligible fixed and verified 93.8%; wrong actions 0; actions without consent 0; injections blocked 100%; cross-sector leakage 0; verifier caught the broken backend in all four sectors; p95 197 ms over 517 calls. Four misses, all escalations on hard paraphrases. |
| LLM drafts | Qwen3-8B on the GX10 drafted the same steps and verifier as the human-taught playbook in all four sectors (20 to 32 s each, 3 in parallel). |
| Defects the first run exposed | saas playbook froze `role == analyst` and refused admins; one-utterance match examples gave telecom 50% recall; a saas complaint on an order matched the ecommerce playbook on "stuck" + "migration" (2 wrong actions). All three fixed; 48 tests pass. |
