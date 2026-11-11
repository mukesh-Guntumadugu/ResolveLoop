# Sixty-second demo video script

Record at 1080p. Two windows: the published eGain demo page (orbit.html with the widget) and the ResolveLoop desk UI. Reset demo data before recording (Audit → Reset demo data).

| Time | Screen | Voice-over |
|------|--------|------------|
| 0–8 s | eGain widget on the Orbit help page. Pre-chat: "Exports and downloads", C001, "My export has been spinning since we migrated." The agent answers from the migration article, then escalates with two options. | "Every time support escalates a new problem to a human, the fix is lost as a one-off ticket. ResolveLoop turns verified fixes into reusable AI actions." |
| 8–21 s | Desk UI, Human desk tab: case C001, run get_profile → check_entitlement → grant_export_permission (consent) → test_export. The trace fills in; the diff shows export_permission false → true. Mark resolved. | "A specialist solves it in the support desk. Every authorized tool action is captured as a structured event, with the verified result." |
| 21–34 s | Learn → candidate appears. Reviewer tab: prerequisites, the single allowlisted action, the verifier, provenance. Click Approve. | "ResolveLoop proposes a procedure: prerequisites, one allowlisted action, a verification step, and provenance. Nothing runs until a reviewer approves it." |
| 34–49 s | eGain widget (or Customer tab): C002, "CSV won't download since migration." Agent matches the approved procedure, asks to confirm, applies the fix, shows "Fixed and verified" and the state after. | "A different customer asks in different words. The agent finds the approved procedure, checks the live account, asks permission, applies the fix and verifies it before saying so." |
| 49–56 s | C003 same message → "Escalating to a specialist", reason: subscription inactive, two contact options. Click "Email ticket": the agent quotes ticket RL-100x; the desk Dashboard tick marks Tickets 1. | "An ineligible account is refused and handed to a human with a real ticket, not guessed at." |
| 56–60 s | Published demo link and title card. | "ResolveLoop: every approved human fix becomes a safer, reusable support capability." |

Do not describe the eGain agent as authoring its own workflows. Say "approved procedure" and "simulated desk". If Actions are not available in the tenant, show the Customer tab of the desk UI for the 34–49 s segment and say so on screen ("external action, called from the process workflow fallback").
