# eGain Agentic Studio: issues and feedback from building on it

Feedback for the eGain team, gathered while building a working AI support agent on the
hackathon tenant (`aidev.egain.cloud/y6ip`) between 2026-11-11 and 2026-11-13. Every item
below is something we actually hit in the console, the workflow editor, Custom API actions
or the published widget while assembling the required pieces (knowledge agent, pre-chat,
escalation, process workflows, actions). Each is tied to the dated evidence in
`egain/OBSERVED.md`. This is about *your* platform; issues in our own backend are tracked
separately and are not in this document.

Order is roughly by how much it cost us during the build.

## 1. Functional bug — API node: request-body text bled into a header value
**Severity: bug (functional).** When we configured the callback API node in the escalation
workflow (`POST /v1/callbacks`), the JSON request body ended up appended to the value of
the `X-Tenant-ID` header. Our server rejected it with `400 BAD_TENANT` because the tenant
value was no longer `demo` but `demo{...json...}`. It took a v3 of the workflow to notice
the header field had picked up the body text. The body and header inputs of the API node
should be isolated; one should never leak into the other.
**Evidence.** OBSERVED.md, upgrade round: "the X-Tenant-ID header of the callback node had
the JSON body appended to its value (400 BAD_TENANT on the server)."
**Repro sketch.** Add an API node, paste a JSON body, then edit a static header value;
the header retains the body text.

## 2. Reliability/UX — no "changes are deploying" state; stale agent returns a misleading error
**Severity: high UX / demo risk.** After saving or assigning a workflow, there is a
propagation delay (eGain states up to 5 minutes; we saw up to ~8). During that window the
Test AI Agent chat and the published widget answer "I am unable to assist you with that"
as if the request failed, when in fact the change is still deploying. In a live demo this
looks like a broken agent. A visible "changes are still propagating" or "deploying" state,
or simply holding the old behaviour until the new one is live, would avoid a false failure.
**Evidence.** OBSERVED.md: "An earlier try 3 min after saving showed 'I am unable to assist
you' (propagation lag, up to 5 min as eGain states)."

## 3. Design note (NOT a proven eGain vulnerability) — action parameters are LLM-filled
**Severity: feedback / hardening request. We did not demonstrate any vulnerability in
eGain's platform.** A Custom API action auto-extracts its parameters and the LLM fills them
from the conversation, so the agent will pass whatever `account_id` a user names. This is
expected behaviour for an LLM action, not a flaw. Whether that can cause harm depends
entirely on the *backend's* authorization, which is the integrator's responsibility, not
eGain's. In our own backend we proved (on our own server, eval tenant) that identity is
self-asserted — the only check is that the claimed principal equals the account named — so
that is **our** bug and it is tracked in `docs/security-review.md`, not here.
**Honest status.** We found no data leak, auth bypass or logical flaw in eGain's own
systems. We did not test eGain's platform for such issues (see the scope note below).
**Optional product suggestion.** It would help integrators if an action parameter could be
*bound* to a verified pre-chat/session variable and marked non-LLM-overridable, so
identity-bearing fields come from a trusted source rather than the conversation.

## 4. Usability — workflow editor publish checks and node deletion
**Severity: usability friction.** Several publish-time rules only surface when you try to
publish, after the graph is built:
- `userQuery` must be assigned before the "Send to AI Agent" node, or publish fails.
- The final Question node's **Invalid** handle must be left unconnected, which is
  counterintuitive (you expect every handle to need a target).
- Every select option must be connected, all nodes reachable, no loops.
Also, a node can only be deleted once it is an orphan: you must first delete its edges, and
an edge is only deletable while selected, with the delete "X" sitting at the edge midpoint.
Rebuilding a mis-wired branch is slower than it should be.
**Ask.** Validate incrementally (flag the `userQuery`/Invalid-handle rules as you wire,
not only at publish) and allow deleting a node together with its edges.
**Evidence.** OBSERVED.md pre-chat and process-workflow rows.

## 5. Onboarding/docs — two consoles with confusable names
**Severity: docs/onboarding.** The agent builder is under Profile → Consoles →
**Agentic Studio** ("AI Agent for Customer"). The separately named **AI Console** is
AssistGPT prompt templates, not the agent builder. It is easy to start in the wrong place.
A clearer label or a pointer from AI Console to Agentic Studio would save first-time users
time.
**Evidence.** OBSERVED.md, first row.

## 6. Content ingestion — limits and lack of pre-training validation feedback
**Severity: minor.** Training accepts up to 10 files, 5 MB each (.html/.pdf/.docx), and a
"Website → Enter list of URLs" importer that crawls the given URLs. The character count of
what was ingested (26,909 for five PDFs; 20,098 for the URL import) is only visible after
training, so there is no up-front signal that a document was read correctly or truncated.
A pre-training preview of extracted text length per source would help authors trust the
corpus before they train.
**Evidence.** OBSERVED.md training rows.

## What worked well (worth keeping)
- The in-editor **Test Request** on API nodes and Custom APIs (HTTP status and latency)
  made wiring an external backend fast; every node we built passed its test before publish.
- Grounded answers cited the exact source documents, which made the knowledge agent easy
  to trust and verify.
- Escalation connector actions (Chat Transfer, Send Email, Trigger Call) and the pre-chat
  → Send to AI Agent hand-off composed cleanly once wired.
- The published demo link reproduced the full console behaviour, including pre-chat, so we
  could validate end to end without the console.

## Scope note
This feedback comes from normal use of the hackathon tenant while building. We did NOT run
any security testing against eGain infrastructure, and we have NOT found or proven any
vulnerability (data leak, auth bypass, injection or logical flaw) in eGain's own systems.
Items 1 and 2 are functional/UX bugs seen during ordinary use; items 3-6 are feedback.
eGain publishes a vulnerability reporting form at https://www.egain.com/vulnerability-reporting/
(response within 2 business days; keep reports private until fixed; do not share customer
data). There is no safe-harbor or authorization-to-test statement, so any security testing
of their platform needs explicit written permission from eGain first.
