# Judging map

The challenge scores Best Overall on **usefulness, execution and Clocked integration**, and scores the three group awards with **breadth inside the group** made explicit. This page points each claim at something a judge can check in under a minute.

## Best Overall App

### Usefulness — who pays, and for what

| Claim | Evidence |
| --- | --- |
| Replaces a 3–6 hour first pass | The pipeline returns a structured, cited first pass in 5–7 seconds on the bundled 220 sqm lease. |
| Sold to a named buyer at a named price | Solo $49/mo for 100 audits; Firm $199/mo for 500 audits and 5 seats; $2 overage. `backend/billing.py`, `#/pricing`. |
| The buyer's real objection is PII | Identifiers are pseudonymised before Extract/Verify/Decide; only masked text is persisted; the re-identification key is returned once and never stored. `backend/pseudonym.py`, `#/method`. |
| The output is a deliverable, not a dashboard | Print-ready HTML (prints to PDF), Markdown and JSON, with a white-label option on Firm. `GET /api/v1/audits/{id}/report.html`. |
| It works without a credit card | Three free audits, demo session, bundled sample, one-command run. |

### Execution — does it hold up

| Claim | Evidence |
| --- | --- |
| Real end-to-end flow | Five live Clocked calls; no mocked results in the request path. |
| Correctness is tested | 40 offline tests: pseudonymisation, claims, every rule, policy escalation, storage isolation, report escaping, quota, API keys. `python -m pytest tests -q`. |
| Failure is designed | Guard fails closed; pipeline errors return the failing step and a sanitised message; Supabase missing → SQLite fallback shown in the header; quota → `402` with the usage payload. |
| It is operable | Accounts, history, exports, plans, usage meter, API keys, health endpoint, Docker + Render config. |
| It is fast | Measured 5–7 s wall time for five sequential calls; 759 ms of model time. |

### Clocked integration — is each call load-bearing

| Endpoint | If it were removed, what would break |
| --- | --- |
| `pii` | Raw tenant identifiers would reach Extract/Verify/Decide and the stored record. |
| `injection` | A poisoned document could steer later steps; the fail-closed path and the blocked state would not exist. |
| `extract` | There would be no claim list, no numeric facts, and no lease-terms table; Verify would fall back to noisy whole-document grounding. |
| `grounding` | There would be no verdicts, no evidence quotes, and the risk policy would have only the model's Decide output. |
| `decide` | There would be no calibrated risk level, action set, or human-review flag; the banner and checklist would be empty. |

The report also records measured Clocked usage per audit (`usage.credits`, `usage.cost_usd`), computed from the `timing` field of each response.

## Group awards — breadth

| Group | Endpoints used | Breadth | What the used endpoints change |
| --- | --- | --- | --- |
| **Decide, Extract, or Fill** | `extract`, `decide` | 2 of 3 (20/30) | Extract's fields become the claims and numbers; Decide's typed answers set the risk banner, the action checklist and the review flag. |
| **Protect, Guard, or Inspect** | `pii`, `injection` | 2 of 3 (20/30) | `pii` produces the tokens every later step sees; `injection` can abort the run before any further call. |
| **Verify, Compare, or Rerank** | `grounding` | 1 of 3 (10/30) | Verify's per-claim verdicts and evidence quotes drive the risk policy and the report's evidence column. |

We did not add `fill`, `inspect`, `compare`, `rerank` or `script` as decoration. Each is a real product feature with a downstream effect; [`ROADMAP.md`](ROADMAP.md) explains where they fit and why they were not bolted on before the deadline.

## What a judge can verify in 60 seconds

1. `python run.py` → open `http://127.0.0.1:8000` — header shows **engine live**.
2. **Workspace → Load sample → Run audit** — five named steps with real timings appear.
3. The verdict says **HIGH · 100**; the rationale names the parking shortfall and the entertainment conflict.
4. **Rule engine** tab shows `ceil(220 ÷ 100 × 2) = 5 required vs 4 allocated`.
5. **Findings** tab shows the contradicted claim with the quote “Live entertainment after 22:00 requires a supplementary entertainment permit…”.
6. **Privacy** tab shows six tokens and no raw identifiers.
7. **Open printable report** renders the same audit as a client-ready document.
8. `GET /api/v1/health` reports the engine, the storage backend and the five steps.

## Honest gaps

- Compare, Fill, Rerank and Inspect are not implemented. The entry claims five endpoints, not nine.
- The rule engine covers the numeric patterns it knows; other jurisdictions need their own rule pack.
- Supabase persistence requires the one-time `supabase/schema.sql` run; until then the product uses SQLite, and says so.
- The report is decision support, not legal advice, and the product says that in the UI and every export.
