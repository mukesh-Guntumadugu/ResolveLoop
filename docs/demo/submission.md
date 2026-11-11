# Submission draft (verify every line against what is built before submitting)

Form: https://www.egain.com/ai-agent-hackathon-project-submission/ — deadline Nov 15, 2026, 11:59 PM PST.

- Lead participant: Mukesh Guntumadugu · Entry size: Individual
- Agent name: **Orbit Support Assistant (ResolveLoop)**
- Industry: Technology
- Use case (≤150 chars): Turn verified human support fixes into approved AI actions that resolve the next similar customer case.
- eGain capabilities demonstrated: Knowledge-based answers, Published experience with Orbit look and feel, Pre-chat workflow, Escalation workflow with ticket and callback API nodes, two Process workflows (export troubleshooter, subscription check) with API nodes and a Condition, three Custom API Actions (all observed working on 2026-11-11, see `egain/OBSERVED.md`)
- Published demo URL: https://aidev.egain.cloud/y6ip/system/web/apps/aiagent/demo.html?agentId=8ba71b10-c3ee-4a3f-b507-8fe3a4d5113a&backgroundUrl=https://cdn.aiagent-dev.egain.cloud/TMDEVEB12725755/screenshots/23a971cf-91ed-4c2b-90dc-2c54439ea014.png
- One-minute video URL: (YouTube, unlisted)
- Pre-existing templates/code/third-party assets: FastAPI, Uvicorn, Pydantic, httpx, pytest, ReportLab, Python-Markdown (open-source libraries). Generative AI coding tools used. All knowledge content original and fictional.

## Solution description (150 words max; this draft is 150)

ResolveLoop is a learning layer behind an eGain AI Agent for Orbit Reports, a fictional SaaS. Support bots escalate unfamiliar problems, and the human fix then stays buried in a ticket. ResolveLoop captures the structured, authorized tool actions a specialist takes in a simulated support desk, pairs them with a verified outcome, and generates a candidate procedure with prerequisites, an allowlisted action, a verifier and provenance. A reviewer must approve it before it can run. When another customer reports the same issue in different words, the agent finds the approved procedure, checks the live account state, asks for confirmation, applies the action and verifies the result. Ineligible, ambiguous or injected requests are refused and escalated with two contact options. The eGain agent supplies grounded answers from Orbit's help articles, pre-chat intake, an export troubleshooting process workflow and escalation. Intended users: support teams who want governed automation that grows from resolutions.

## Reviewer instructions (optional field; no passwords)

1. Open the published demo link. In pre-chat choose "Exports and downloads", account ID C001, then say: "My export has been spinning since we migrated." Expect a grounded answer that does not invent a fix, then the escalation workflow with two options (email ticket, phone or callback).
2. Ask "Which roles can export reports?" to see a content-based answer.
3. Ask "Export is not working" to enter the Orbit Export Troubleshooter process workflow.
3b. Ask "Is my subscription active?" (account C003 or C012) to see the agent call the account-status action, or "I need to reactivate my subscription" to enter the Orbit Subscription Check workflow (live API call, condition on the active flag).
3c. Say "I want to speak to an agent", choose "Email ticket": the escalation workflow opens a ticket in ResolveLoop and quotes its number (RL-100x); "Phone or callback" asks for a number and schedules a callback (CB-100x).
4. Open the simulated support desk at https://srv1619809.hstgr.cloud/resolveloop/ui/ (read-only without the demo key; organizers may request it). The Dashboard shows live counts (cases, approved playbooks, verified resolutions, refusals, unsafe executions = 0, tickets, callbacks); the Audit tab shows the approved playbook, its source trace and executions.
5. With the demo key: Audit → Reset demo data; Human desk → new case for C001 → run the four tools → Learn; Reviewer → Approve; Customer tab → C002 "I can't download the CSV after we migrated" → confirm → verified fix; C003 same message → refused with escalation options.
Sample case IDs only (C001, C002, C003). No real credentials or customer data anywhere.

## Evidence checklist (section 05.6 of the design package)

- [ ] Published eGain demo link tested after propagation
- [ ] Video (60 s) uploaded
- [ ] Screenshot: approved playbook + source trace (Reviewer tab)
- [ ] Screenshot: account state before/after (Customer tab, state_after)
- [ ] `evidence/junit.xml` from the last test run (24 tests; paraphrase set 10/10 matched, 0/10 false positives)
- [ ] `egain/OBSERVED.md` filled in; limitations copied into the README
