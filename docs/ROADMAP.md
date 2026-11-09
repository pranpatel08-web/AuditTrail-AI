# Roadmap

What is deliberately not in the submission, and the test each addition has to pass: **does the endpoint's output change what the product does, or is it decoration?**

## Next: Compare (third endpoint in the Verify group)

Leases arrive as revisions. The highest-value next feature is a redline audit:

1. Upload draft v1 and draft v2 (or the executed lease and an amendment).
2. `POST /clocked/compare` returns the material differences.
3. Each difference is run through the existing claim builder and rule engine, so the report answers: *which amendments introduce a compliance issue, and which cure one?*

Why it earns its place: it is the third endpoint in the Verify group (full breadth), it uses the same storage and report pipeline, and it matches how diligence actually happens. It is a schema change (`at_audits.parent_id`) plus one gateway method and one UI state.

## Then: Fill

The report ends with a remediation checklist that a human retypes into a letter. `POST /clocked/fill` can produce the notice from the same structured facts: recipient, premises, clause, required cure, deadline. Pricing fits the Firm plan ("generate the cure notice"), and the output is still verified against the lease.

## Then: Rerank

A 40-page lease produces more clauses than a reviewer can read in order. `POST /clocked/rerank` against the extracted clauses, ordered by financial exposure and rule-failure severity, gives the reviewer a queue instead of a document. This is a UI feature more than an API feature; it needs the clause extraction to be broadened beyond twelve fields.

## Considered and rejected for now

- **Inspect (script)** — the product never executes documents, so script inspection would be a call whose output changes nothing.
- **Guard on images** — no OCR pipeline yet; adding it would slow the core loop without a buyer asking.
- **A second LLM provider** — the pipeline is provider-agnostic in one module, but a fallback provider doubles evaluation work before there is revenue to justify it.

## Product work that is not an endpoint

| Item | Why |
| --- | --- |
| Jurisdiction rule packs | The rule engine is data-shaped but currently hard-coded for the demo. Packs make it sellable outside Lusaka. |
| Reviewer queue and roles | Firm plan needs assignment, comments and sign-off, not just shared history. |
| Stripe webhooks | Sandbox plan switching works; live billing needs `checkout.session.completed` and subscription lifecycle handling. |
| PDF upload with OCR | Buyers have PDFs, not text. Text paste is a demo shortcut, not a product. |
| SOC 2 readiness | Required before Enterprise; the data model (no raw PII, no vault) is already aligned. |
| On-prem packaging | Enterprise tier promise; Docker image plus a licence check. |

## Explicit non-goals

- A general-purpose contract chatbot. The value is the audit trail, not conversation.
- Drafting lease clauses. The product checks documents; it does not become the author of the document it later audits.
- Replacing counsel. Every export says decision support, not legal advice, and the human-review flag is a product feature, not a disclaimer.
