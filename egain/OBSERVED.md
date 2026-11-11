# What was actually observed in the hackathon tenant

Fill in while building; the submission must only claim what is recorded here.

| Capability | Observed? | Notes / screenshot |
|-----------|-----------|--------------------|
| Trial tenant sign-in (AI Agent console) | yes | Profile menu → Consoles → **Agentic Studio** ("AI Agent for Customer"); "AI Console" is AssistGPT prompt templates, not the agent builder. Tabs: AI Agents, Workflows, External Credentials. |
| Train on 5 uploaded PDFs | yes | Setup wizard: Point to Content → Files and Website → Files. Accepts .html/.pdf/.docx, up to 10 files, 5 MB each. 5 PDFs = 26,909 chars; "Train AI Agent" started 2026-11-11. |
| Generated intents include an export topic | yes | 5 intents generated: Export Configuration and Troubleshooting; Subscription and Billing Management; User Roles and Access Control; Platform Migration and Updates; Technical Support and Escalation. Test chat: "Which roles can export reports?" → grounded answer citing 03 and 01 PDFs. Probe "export spinning since we migrated" → says contact Orbit Support with account ID, no invented fix (cites 02, 01). |
| Published demo link works | created | Demo link: https://aidev.egain.cloud/y6ip/system/web/apps/aiagent/demo.html?agentId=8ba71b10-c3ee-4a3f-b507-8fe3a4d5113a&backgroundUrl=https://cdn.aiagent-dev.egain.cloud/TMDEVEB12725755/screenshots/23a971cf-91ed-4c2b-90dc-2c54439ea014.png (background = screenshot of orbit.html). Default escalation phone +1 555 010 0199, email support@orbit-analytics.example set; cannot-answer message customised; 521-char guidance in Additional instructions. |
| Pre-chat workflow attached | | |
| Escalation workflow: Direct + Knowledge Gap, two options | | |
| Process workflow attached to the export intent | | |
| Actions: outbound HTTP call to ResolveLoop (Path A) | | |
| Fallback used (Path B) | | |
