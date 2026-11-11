# Rehearsal run sheet (walked live on 2026-11-11, hosted desk UI)

Desk UI: https://srv1619809.hstgr.cloud/resolveloop/ui/ — enter tenant `demo` and the API key from `.env` once; it is remembered.
Published eGain link: see `docs/demo/submission.md`. Widget: pre-chat → "Exports and downloads" → account ID → one line.

| Beat (video script) | Clicks | What appears | Screenshot |
|---|---|---|---|
| 0. Prep | Audit tab → **Reset demo data** | toast "16 accounts seeded; playbooks cleared" | — |
| 1. 0–8 s | Customer tab → Account `C001` → chip "Export button spins forever" → **Send** | "Escalating to a specialist", NO_PLAYBOOK, two contact options | rehearsal-1-c001-escalate.jpg |
| 2. 8–21 s | Human desk → **Create case** (prefilled C001) → **Escalate** → Run `accounts.get_profile` → Run `accounts.check_entitlement` → tick **Customer consent** → Run `accounts.grant_export_permission` → Run `reports.test_export` | Live trace shows 5 events; event 4 shows `export_permission: false → true`; toast "export_ok: true" | rehearsal-2-desk-trace.jpg |
| 3. 21–34 s | **Mark resolved** → **Learn procedure** → Reviewer tab → select the REVIEW_PENDING row → **Approve** | HTTP 202 candidate card; reviewer shows prerequisites, one step, verifier, stop conditions, "passes all policy checks", then APPROVED with provenance (4 events) | rehearsal-3-candidate.jpg, rehearsal-4-approved-provenance.jpg |
| 4. 34–49 s | Customer tab → Account `C002` → chip "Can't download CSV after migration" → **Send** → **Yes, apply the fix** | "Approved fix found … May I apply it?" then "Fixed and verified", execution SUCCEEDED, state after with `export_permission=true` | rehearsal-5-c002-resolved.jpg |
| 5. 49–56 s | Account `C003` → same chip → **Send** | "Escalating to a specialist": active is False, needs True; EXP-200; execution BLOCKED; two contact options | rehearsal-6-c003-refused.jpg |
| 6. 56–60 s | Switch to the published eGain link | pre-chat buttons and the Orbit help page | egain-published-link-prechat.jpg |

Alternative for beat 4, using eGain itself (recorded earlier in the console test chat): after pre-chat as C002, type "Export is not working"; the agent calls the ResolveLoop action, asks "May I apply the approved fix…?", and on **Yes** reports it applied and verified. Allow 10–15 s for the two action calls.

Timing from this run: the whole loop takes about 90 seconds unhurried, so the 60-second video needs cuts between beats; each API call returns in about one second.
Known UI note: the "Try" chips only fill the message; **Send** still has to be clicked.
