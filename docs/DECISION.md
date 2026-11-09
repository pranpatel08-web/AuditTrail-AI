# Decision: which version to submit

**Recommendation: submit the FastAPI version, with the browser client served by FastAPI itself. Do not submit the Streamlit dashboard.**

This is the decision the brief asked for, with the evidence behind it and what changed during the build.

## The two candidates

| | Streamlit dashboard | FastAPI product |
| --- | --- | --- |
| Entry point | `app.py` (135 lines), `updated app.py` | `run.py` → `backend/main.py` |
| Clocked endpoints | 3 (`/protect`, `/verify`, `/decide`) | 5 (`pii`, `injection`, `extract`, `grounding`, `decide`) |
| Client | Streamlit widgets | PWA served by FastAPI: landing, workspace, history, pricing, billing, report |
| Auth | none | Supabase Auth (email/password) + hashed API keys |
| Persistence | none | Supabase Postgres with RLS, SQLite fallback |
| Billing | none | plans, quotas, metering, Stripe Checkout adapter |
| Report | a Markdown download | print-ready HTML/PDF, Markdown, JSON; white-label on Firm |
| Tests | none | 40 offline tests |
| Runs today | no — `httpx` and `streamlit` were not installed, and `st.columns()` is called with no arguments in the results branch | yes — verified live end to end |

## Why FastAPI wins for this challenge

1. **Breadth is scored explicitly.** The challenge awards breadth within each endpoint group: using all three endpoints of a group earns the full 30 points. The FastAPI pipeline uses five endpoints and covers all three groups (Protect + Guard; Extract + Decide; Verify). The Streamlit app touches three endpoints from two groups and calls them by raw HTTP path.
2. **"Meaningful use" means the output changes what happens next.** In the FastAPI pipeline, Guard can abort the run, Extract decides which claims are tested, Verify's verdicts drive the policy, and Decide sets the banner and checklist. In the Streamlit app the three responses are printed; none of them changes a later step.
3. **Best Overall weighs usefulness and execution.** A dashboard that cannot store an audit, identify a user or export a report is a demo. The product has accounts, quotas, history, exports and a pricing surface — the things a buyer needs before paying.
4. **It survives the demo.** The Streamlit version has no dependency pinning, no error surface beyond a red box, and a runtime bug in the results layout. The FastAPI version fails closed with a sanitised error, reports which step failed, falls back to SQLite if Supabase is unavailable, and has 40 tests.
5. **Monetisation was part of the brief.** There is nowhere to put a plan, a quota or an account in a single-file Streamlit script.

## What about the Node/Next.js half?

The FastAPI + Node version existed as a **prebuilt static Next export** (`audittrail perplexity/AuditTrail AI/`) with no source tree. It contained a polished four-page UI and expected exactly three routes: `/api/v1/health`, `/api/v1/audit/process`, `/api/v1/audits`. It could be served, but not modified, extended with pricing/billing, or rebuilt with new environment values.

Rather than submit an unmaintainable build artifact, the client was rewritten as a **zero-build PWA** served by FastAPI:

- no Node toolchain, no build step, no CDN dependency — `python run.py` serves the whole product;
- the same design language (paper, ink, serif display, mono data) and the same API contract;
- new surfaces the Next export lacked: pricing, billing, usage, API keys, printable report, method page.

This keeps the "FastAPI + browser client" architecture the brief described, removes the fragile part, and makes the repository something a judge can run in one command.

## Scoring matrix

Weights reflect the published judging: usefulness, execution and Clocked integration for Best Overall, with breadth scored per group.

| Criterion | Weight | Streamlit | FastAPI + PWA |
| --- | ---: | ---: | ---: |
| Usefulness to a real buyer | 30 | 8 | 27 |
| Execution and polish | 25 | 9 | 23 |
| Clocked integration depth | 25 | 10 | 24 |
| Breadth across endpoint groups | 10 | 4 | 9 |
| Business viability | 10 | 1 | 9 |
| **Total** | **100** | **32** | **92** |

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Live API fails during judging | Guard and errors fail closed with a clear step; the demo video is recorded in advance; SQLite keeps history working. |
| Supabase schema not applied | Automatic fallback to SQLite, reported in the header and `/api/v1/health`; one SQL file applies the production schema. |
| Demo network is slow | The pipeline is five sequential calls (~5–7 s); the UI shows real step progress and timings. |
| Judges cannot run it | `python run.py` after `pip install -r requirements.txt`; sample documents are bundled; demo mode needs no account. |
| Credit exhaustion | A measured audit costs ~31 credits; the challenge grant is 20,000. |

## What to do with the Streamlit version

It is kept locally in `legacy/` (excluded from git: its handoff notes contain live keys) as a record of the first prototype, and it is not submitted. If a fallback demo is ever needed, it needs two fixes first: install `httpx` (it was missing from the original environment) and replace `st.columns()` with `st.columns(2)`. Even fixed, it demonstrates less of the API surface and has no product around it.

## Deadline

Entries close **10 November 2026, 11:59 p.m. Eastern Time** ([challenge page](https://clocked.rezolve.ai/challenge)). Submit the repository, the demo video, the hosted URL if available, and the "how you used Clocked" section from [`SUBMISSION.md`](SUBMISSION.md).
