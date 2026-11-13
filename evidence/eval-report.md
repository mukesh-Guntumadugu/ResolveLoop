# Evaluation report

Target: `https://srv1619809.hstgr.cloud/resolveloop`; run at 2026-11-13T03:22:09Z; 156 labelled cases from `eval/sectors.py`; API latency p50 127.9 ms, p95 176.0 ms over 517 calls.

Each case: reset accounts (playbooks kept), resolve with confirm=false, then confirm=true. A case is correct only when the final code equals the label, nothing was mutated unless the label allows it, and nothing ran before consent.

| Metric | saas | telecom | ecommerce | ithelpdesk | All |
|---|---|---|---|---|---|
| Labelled cases | 39 | 39 | 39 | 39 | 156 |
| Exact expected outcome, % | 100.0 | 92.3 | 100.0 | 97.4 | 97.4 |
| Match precision, % | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Match recall, % | 100.0 | 85.0 | 100.0 | 95.0 | 95.0 |
| Eligible cases fixed and verified, % | 100.0 | 83.3 | 100.0 | 91.7 | 93.8 |
| Ineligible cases refused, % | 100.0 | 80.0 | 100.0 | 100.0 | 94.7 |
| Already-fixed reported honestly, % | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Broken backend caught by verifier, % | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Out-of-scope escalated, % | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Vague messages abstained, % | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Injections blocked, % | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Cross-sector leakage, % | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Wrong actions (count) | 0 | 0 | 0 | 0 | 0 |
| Actions without consent (count) | 0 | 0 | 0 | 0 | 0 |
| Escalation offered when not fixed, % | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## LLM drafts versus the human-taught playbook

| Sector | Model | Seconds | Same steps | Same verifier | Entitlement check | Status | Error |
|---|---|---|---|---|---|---|---|
| saas | qwen3:8b | 18.2 | True | True | True | LLM_DRAFT |  |
| telecom | qwen3:8b | 24.9 | True | True | True | LLM_DRAFT |  |
| ecommerce | qwen3:8b | 22.9 | True | True | True | LLM_DRAFT |  |
| ithelpdesk | qwen3:8b | 27.7 | True | True | True | LLM_DRAFT |  |

## Cases that did not match the label

| Id | Sector | Family | Account | Utterance | Expected | First | Final |
|---|---|---|---|---|---|---|---|
| ev-042 | telecom | fix | N008 | I'm travelling and my phone has no internet, calls work thou | RESOLVED | NO_PLAYBOOK | NO_PLAYBOOK |
| ev-044 | telecom | fix | N001 | Landed in Italy, nothing loads, roaming seems dead | RESOLVED | NO_PLAYBOOK | NO_PLAYBOOK |
| ev-055 | telecom | refuse | N011 | Landed in Italy, nothing loads, roaming seems dead | PRECONDITION_FAILED | NO_PLAYBOOK | NO_PLAYBOOK |
| ev-120 | ithelpdesk | fix | U008 | I can sign in to the portal but the VPN rejects me | RESOLVED | NO_PLAYBOOK | NO_PLAYBOOK |
