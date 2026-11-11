# ResolveLoop — human-to-AI support learning

Entry for the eGain hackathon **"Build, Demo, and Take Home a Working AI Support Bot"** (Devpost, Nov 2026).

ResolveLoop is a learning layer behind an eGain AI Agent. When the agent escalates a problem it cannot solve,
a human specialist fixes it in a simulated support desk. The desk records the specialist's **structured tool
actions** (never screen pixels), proposes a **candidate playbook**, and a reviewer must **approve** it before it
can run. The next customer with the same problem in different words gets the approved fix applied, **verified**,
and audited. Ineligible or ambiguous cases are refused and escalated instead of guessed.

Demo domain: a fictional SaaS, **Orbit Analytics / Orbit Reports**, whose Cloud 2 migration silently drops the
per-user export permission. All data, accounts and contact details are synthetic (see `docs/domain.md`).

## Layout

| Path | What |
|------|------|
| `server/` | FastAPI orchestrator: `mock_business` (synthetic accounts + allowlisted tools), `trace` (action events, audit), `learning` (deterministic trace → playbook extractor), `review` (approval state machine, versioning), `resolve` (paraphrase matcher, gated executor, verifier) |
| `web/` | Simulated support desk (dashboard with live metrics, customer simulator, human desk, reviewer, audit) and the Orbit help center page the eGain widget sits on (static, served at `/ui/`) |
| `tests/` | pytest: E2E-01…06, safety/negative cases, paraphrase set |
| `knowledge/` | The fictional help articles the eGain agent is trained on (Markdown + generated PDFs) |
| `egain/` | Workflow blueprints for the eGain console (pre-chat, escalation, process tools, action) and reviewer instructions |
| `contracts/openapi.json` | API contract exported from the app |
| `deploy/` | systemd unit, nginx location, VPS deploy script |
| `docs/` | Domain definition, demo script, submission text |

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install fastapi "uvicorn[standard]" pydantic httpx pytest
RESOLVELOOP_API_KEY=demo-key .venv/bin/uvicorn server.main:app --port 8790 --reload
```

Open http://127.0.0.1:8790/ui/ and enter `demo-key` in the settings strip. API docs: http://127.0.0.1:8790/docs.

Tests (writes `evidence/junit.xml`):

```bash
.venv/bin/python -m pytest -q -s tests --junitxml=evidence/junit.xml
```

## The loop in five calls

1. `POST /v1/resolve` with a new problem → `NO_PLAYBOOK`, escalation options (nothing is mutated).
2. Specialist in the desk: `accounts.get_profile` → `accounts.check_entitlement` → `accounts.grant_export_permission` (consent) → `reports.test_export`; each call becomes an `ActionEvent`.
3. `POST /v1/cases/{id}/learn` → `202 REVIEW_PENDING` candidate with prerequisites, steps, verifier, provenance.
4. `POST /v1/playbooks/{id}/approve` → `APPROVED` (identity and time recorded).
5. `POST /v1/resolve` with a paraphrase → `CONFIRM_REQUIRED`, then with `confirm=true` → `RESOLVED` with `verified: true`; an inactive account gets `PRECONDITION_FAILED` and escalation.

State machines: Case `NEW → AGENT_ATTEMPTED → ESCALATED → HUMAN_WORKING → HUMAN_RESOLVED → CLOSED` (alt. `NEEDS_HUMAN`, `FAILED_VERIFICATION`);
Playbook `REVIEW_PENDING → APPROVED → RETIRED` (`REJECTED` terminal); Execution `PROPOSED → AUTHORIZED → RUNNING → VERIFYING → SUCCEEDED` (alt. `BLOCKED`, `FAILED`).

## Known limitations (honest list)

- The extractor is deterministic (`deterministic-v1`). It generalizes nothing on its own: prerequisites are the observed state, and a reviewer widens them (e.g. role analyst → analyst or admin) through a new version.
- Paraphrase matching is concept-overlap over reviewer-editable examples, not embeddings. Measured on the bundled set: see the test output.
- Actions are captured only at the mock tool boundary of one simulated desk. No desktop or screen observation.
- The eGain integration depth depends on what the hackathon tenant exposes; `egain/OBSERVED.md` records what was actually observed working: three Custom API actions (resolve export issue, check account status, open ticket), three process/escalation workflows that call the API node (export troubleshooter, subscription check, escalation with ticket and callback), branded widget.
- Tickets and callbacks are stored in ResolveLoop only; no email or telephony is sent (the eGain Send Email and Trigger Call connectors are configured with fictional contacts).
- Prototype security only: a shared API key, synthetic identities, no SSO. The eGain Custom API action lets the
  agent fill `account_id` from the conversation, so a customer can name another synthetic account; ResolveLoop only
  enforces the owner check when `principal_id` is supplied (the process workflow uses the pre-chat `accountId`).

## Disclosure

Built with FastAPI, Uvicorn, Pydantic, httpx, pytest, ReportLab and Python-Markdown. Generative AI coding tools were used
to write code and documentation. All knowledge content is original and fictional. MIT license.
