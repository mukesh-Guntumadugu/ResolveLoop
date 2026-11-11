# ResolveLoop knowledge base

This folder holds the help-center articles for **Orbit Analytics**, the fictional SaaS vendor used in the ResolveLoop demo for the eGain AI Agent hackathon. `src/` contains the five articles as Markdown (exporting reports, the Orbit Cloud 2 migration, roles and permissions, plans and subscription status, and getting help), and `pdf/` contains the same articles rendered as PDFs for upload to the eGain knowledge store. All content is fictional and was authored for the hackathon: the company, product, account IDs, contact details (`support@orbit-analytics.example`, `(555) 010-0199`) and every policy described here are invented, and no real organisation, person or URL is referenced. The migration article deliberately does not explain how support restores a lost export permission; that gap is what the demo's learning loop is designed to close.

Rebuild the PDFs from the repository root with:

```sh
.venv/bin/python knowledge/build_pdfs.py
```
