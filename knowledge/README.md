# ResolveLoop knowledge base

This folder holds the help-center articles for **Orbit Analytics**, the fictional SaaS vendor used in the ResolveLoop demo for the eGain AI Agent hackathon. `src/` contains the five articles as Markdown (exporting reports, the Orbit Cloud 2 migration, roles and permissions, plans and subscription status, and getting help), and `pdf/` contains the same articles rendered as PDFs for upload to the eGain knowledge store. All content is fictional and was authored for the hackathon: the company, product, account IDs, contact details (`support@orbit-analytics.example`, `(555) 010-0199`) and every policy described here are invented, and no real organisation, person or URL is referenced. The migration article deliberately does not explain how support restores a lost export permission; that gap is what the demo's learning loop is designed to close.

Rebuild the PDFs from the repository root with:

```sh
.venv/bin/python knowledge/build_pdfs.py                   # Orbit (saas): src/ -> pdf/
.venv/bin/python knowledge/build_pdfs.py --domain telecom  # Nimbus Mobile: telecom/src/ -> telecom/pdf/
.venv/bin/python knowledge/build_pdfs.py --domain ecommerce   # Harbor Goods: ecommerce/src/ -> ecommerce/pdf/
.venv/bin/python knowledge/build_pdfs.py --domain ithelpdesk  # Northgate IT: ithelpdesk/src/ -> ithelpdesk/pdf/
```

## Domains and content buckets

The knowledge base now covers four fictional companies so the same learning loop can be shown on SaaS, telecom, online retail and an internal IT helpdesk:

| Domain | Company | Public articles | Internal runbooks | Restricted policy | Manifest |
|--------|---------|-----------------|-------------------|-------------------|----------|
| `saas` | Orbit Analytics (Orbit Reports) | `src/` and `pdf/` (unchanged; the live eGain agent and the `/kb/` URLs depend on these paths) | `saas/internal/` | `saas/restricted/` | `manifest-saas.json` |
| `telecom` | Nimbus Mobile | `telecom/src/` and `telecom/pdf/` | `telecom/internal/` | `telecom/restricted/` | `manifest-telecom.json` |
| `ecommerce` | Harbor Goods | `ecommerce/src/` and `ecommerce/pdf/` | `ecommerce/internal/` | `ecommerce/restricted/` | `manifest-ecommerce.json` |
| `ithelpdesk` | Northgate University IT | `ithelpdesk/src/` and `ithelpdesk/pdf/` | `ithelpdesk/internal/` | `ithelpdesk/restricted/` | `manifest-ithelpdesk.json` |

Every document belongs to exactly one of three **buckets**:

- **public**: customer-facing help-center articles. This is the only bucket that is ever uploaded to the eGain knowledge store or otherwise given to the eGain AI agent. These are the documents rendered to PDF.
- **internal**: runbooks for human specialists (and for the specialist-side learning loop). They name the exact tool ids a procedure may call, the prerequisites, the single permitted mutation, the verifier, and when to stop and escalate. Never given to the customer-facing agent. Markdown only, `"pdf": null`.
- **restricted**: human-only policy (credits, refunds, ownership changes). Explicitly off limits to any automated agent; the only automated action on these topics is escalation. Markdown only, `"pdf": null`.

Each manifest lists its domain's documents with these fields: `id` (stable key, e.g. `telecom-01`, `saas-rb-s1`), `file` (path relative to `knowledge/`), `pdf` (rendered copy for public documents, `null` otherwise), `title` (the article's H1), `bucket` (`public` | `internal` | `restricted`), `source` and `owner` (fictional provenance), `approved_by`, `approved_at` and `version` (review metadata), and `audience` (`customers`, `specialists` or `humans-only`). Anything that loads knowledge into the eGain agent should filter on `bucket == "public"` and ignore everything else.

The telecom story mirrors the Orbit export story: after Nimbus's Core Network Upgrade 5 some lines silently lost roaming provisioning (error RM-100), and the public article deliberately stops at "contact support"; the internal runbook RB-T1 is what closes the gap. Nimbus contact details (`support@nimbus-mobile.example`, `(555) 010-0288`) and the line IDs `N001` to `N012` are invented.

The two newer domains follow the same pattern. At Harbor Goods, some paid orders copied into the new warehouse system during the WMS 4 cutover lost their dispatch queue entry (error SH-100) and never get a shipping label; runbook RB-E1 re-queues dispatch, while refunds and address changes stay human-only. At Northgate University IT, some accounts moved to SSO 2 came across without their VPN access group (error AC-100); runbook RB-I1 re-syncs the group, while password resets and recovery e-mail changes stay human-only. Contact details (`support@harbor-goods.example`, `(555) 010-0377`, `helpdesk@northgate-u.example`, `(555) 010-0466`), the order IDs `H001` to `H012` and the user IDs `U001` to `U012` are invented.
