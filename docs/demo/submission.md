# Submission draft (verify every line against what is built before submitting)

Form: https://www.egain.com/ai-agent-hackathon-project-submission/ — deadline Nov 15, 2026, 11:59 PM PST.

- Lead participant: Mukesh Guntumadugu · Entry size: Individual
- Agent name: **Orbit Support Assistant (ResolveLoop)**
- Industry: Technology
- Use case (≤150 chars): Turn verified human support fixes into approved AI actions that resolve the next similar customer case.
- eGain capabilities demonstrated: Knowledge-based answers, Published experience, Pre-chat workflow, Escalation workflow, Process workflow, Actions (tick Actions only if `egain/OBSERVED.md` records it working)
- Published demo URL: (from Personalize & Publish → Demo Link)
- One-minute video URL: (YouTube, unlisted)
- Pre-existing templates/code/third-party assets: FastAPI, Uvicorn, Pydantic, httpx, pytest, ReportLab, Python-Markdown (open-source libraries). Generative AI coding tools used. All knowledge content original and fictional.

## Solution description (150 words max; this draft is 149)

ResolveLoop is a learning layer behind an eGain AI Agent for Orbit Reports, a fictional SaaS. Support bots escalate unfamiliar problems, and the human fix then stays buried in a ticket. ResolveLoop captures the structured, authorized tool actions a specialist takes in a simulated support desk, pairs them with a verified outcome, and generates a candidate procedure with prerequisites, an allowlisted action, a verifier and provenance. A reviewer must approve it before it can run. When another customer reports the same issue in different words, the agent finds the approved procedure, checks the live account state, asks for confirmation, applies the action and verifies the result. Ineligible, ambiguous or injected requests are refused and escalated with two contact options. The eGain agent supplies grounded answers from Orbit's help articles, pre-chat intake, an export troubleshooting process workflow and escalation. Intended users: support teams who want governed automation that grows from real resolutions.

## Reviewer instructions (optional field; no passwords)

1. Open the published demo link. In pre-chat choose "Exports and downloads", account ID C001, then say: "My export has been spinning since we migrated." Expect a grounded answer that does not invent a fix, then the escalation workflow with two options (email ticket, phone or callback).
2. Ask "Which roles can export reports?" to see a content-based answer.
3. Ask "Export is not working" to enter the Orbit Export Troubleshooter process workflow.
4. Open the simulated support desk at https://srv1619809.hstgr.cloud/resolveloop/ui/ (read-only without the demo key; organizers may request it). The Audit tab shows the approved playbook, its source trace and executions.
5. With the demo key: Audit → Reset demo data; Human desk → new case for C001 → run the four tools → Learn; Reviewer → Approve; Customer tab → C002 "I can't download the CSV after we migrated" → confirm → verified fix; C003 same message → refused with escalation options.
Sample case IDs only (C001, C002, C003). No real credentials or customer data anywhere.

## Evidence checklist (section 05.6 of the design package)

- [ ] Published eGain demo link tested after propagation
- [ ] Video (60 s) uploaded
- [ ] Screenshot: approved playbook + source trace (Reviewer tab)
- [ ] Screenshot: account state before/after (Customer tab, state_after)
- [ ] `evidence/junit.xml` from the last test run (20 tests; paraphrase set 10/10 matched, 0/10 false positives)
- [ ] `egain/OBSERVED.md` filled in; limitations copied into the README
