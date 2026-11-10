# Devpost submission copy

> **Deadline: 10 Nov 2026, 11:59 p.m. ET.** For the ordered, 10-minute version of what is left, see [`SUBMIT_NOW.md`](SUBMIT_NOW.md).

Paste-ready text for the Clocked Build Challenge entry form. Replace the bracketed placeholders (URLs, team details) before submitting.

---

## Project name

**AuditTrail AI**

## Tagline (one line)

Lease compliance with receipts: five Clocked calls, deterministic arithmetic, every finding cited.

## Elevator pitch (≤ 200 chars)

AuditTrail audits a commercial lease against the zoning source you supply — masking tenant PII first, citing every claim, and computing the numeric rules itself. A defensible first pass in five seconds.

## Awards to select

- **Best Overall App**
- **Best Use of Decide, Extract, or Fill** — Extract reads twelve verbatim fields; Decide sets risk, actions and review routing.
- **Best Use of Protect, Guard, or Inspect** — Protect pseudonymises before analysis; Guard fails closed on injection.
- **Best Use of Verify, Compare, or Rerank** — Verify returns a verdict and evidence quote for every operative claim.

All three endpoint groups are used meaningfully, so the entry qualifies for every judged award and earns full breadth within two groups and two of three in the third.

## Inspiration

Commercial lease diligence is expensive because it is slow and repetitive, not because it is intellectually hard. An associate reads a 40-page lease against a municipal zoning extract, checks permitted use, parking ratios, signage limits, delivery windows and assignment consent, and writes a memo. Three to six hours per deal, most of it locating clauses.

Generic LLMs made this worse before they made it better: they summarise confidently, cite nothing, and cannot be handed a tenant's name, SSN and bank details. The gap was not "an AI that reads contracts" — it was an audit a lawyer could defend line by line, on documents that never leave the firm.

## What it does

1. Paste a lease and the regulatory source it must satisfy (or load the bundled synthetic sample).
2. The pipeline **masks** tenant identifiers, **screens** for prompt injection, **reads** twelve lease fields verbatim, **verifies** each operative claim against the source, and **decides** the risk level with calibrated probabilities.
3. A deterministic rule engine computes the numeric checks — parking ratios, process-area caps, permitted hours, signage limits, consent standards — and shows the formula.
4. The result is a risk banner with a score, a claim-by-claim table with evidence quotes, a rule table with arithmetic, a remediation checklist, the masked document, and a one-time re-identification key that the server never stores.
5. The audit is persisted to the account, appears in history, and exports as print-ready HTML/PDF, Markdown or JSON. Plans, quotas and hashed API keys are enforced server-side.

## How we used Clocked

Every analysis step is a real Clocked call. The output of each call changes what the next one does — nothing is displayed and ignored.

| # | Endpoint | What we send | What comes back | What it changes |
| --- | --- | --- | --- | --- |
| 1 | `POST /clocked/pii` | Lease text, ten entity kinds, instructions to ignore defined role terms | Entity spans with type, offsets and confidence | Spans become stable tokens (`[ORG_1]`, `[PERSON_1]`); only the masked text reaches steps 3–5. The tenant stays distinguishable from the landlord. |
| 2 | `POST /clocked/injection` | The masked text, evidence enabled | Verdict, injection probability, category | A dangerous verdict **stops the audit** before extract/verify/decide and routes it to human review. |
| 3 | `POST /clocked/extract` | Masked text, twelve named fields, "copy verbatim, never guess" | Values with start/end offsets and confidence | Fills the lease-terms table, builds the claim list for Verify, and supplies the numbers for the rule engine. Missing fields become a documentation-risk action. |
| 4 | `POST /clocked/grounding` | The regulatory source as a document, 4–8 operative claims, an evidence-backed summary | Per-claim `supported` / `contradicted` / `not_stated`, probabilities, evidence quote with offsets | Contradicted claims drive the risk policy and the report's evidence column. Claims the source cannot address are filtered out *before* the call (probes per claim), so the report is not padded with meaningless "not stated" verdicts. |
| 5 | `POST /clocked/decide` | Masked text, extracted fields, grounding verdicts, deterministic rule failures, four typed questions | Typed answers with probabilities: risk level, compliance detected, required actions, human review | Sets the risk banner, the remediation checklist and the review flag. The application's policy layer can escalate a decision on a hard rule failure; it never silently downgrades one. |

**Measured usage:** the sample audit consumed **24–32 credits** across the five calls (588–800 ms of model time) — **$0.007–$0.010** on the Build plan at $0.30 per 1,000 credits. The number is computed from the `timing` field of each response and shown in the report.

## How we built it

- **Backend:** Python 3.13, FastAPI, the official `clocked-sdk`. The gateway normalises every response shape and converts failures into one sanitised `PipelineError` with the failing step.
- **Pseudonymisation:** a dedicated module merges detector fragments, drops defined role terms (`Tenant`, `Landlord`) that would otherwise collapse into the same token, adds deterministic regex backstops for email/phone/SSN/Luhn-valid cards/IP/addresses, assigns tokens left-to-right, and rebuilds offsets against the masked text.
- **Hybrid verification:** `rules.py` computes the numeric checks in code; `policy.py` combines them with the model's probabilities into a 0–100 score, a level and an action list, and records why it escalated.
- **Storage:** a small protocol with two implementations — Supabase Postgres with row-level security, and SQLite for offline/CI. The active backend is reported at `/api/v1/health`.
- **Auth:** Supabase access tokens are verified server-side; a client-supplied `user_id` is ignored. Paid plans can mint `at_…` API keys, stored only as SHA-256 digests.
- **Frontend:** a zero-build PWA (ES modules, one CSS file) served by FastAPI — landing, workspace with live step progress, history, printable report, pricing, billing, API keys, method page. No CDN, no Node build step.
- **Billing:** plan definitions, server-side quota enforcement (`402 quota_exceeded`), usage metering, and Stripe Checkout when keys are configured; an explicitly-labelled sandbox otherwise.
- **Tests:** 40 offline tests with a fake Clocked gateway.

## Challenges we ran into

**Masking destroyed the meaning of the document.** The first Protect run replaced both party names with the same `<ORGANIZATION>` placeholder, and it also masked the defined term "Tenant" — so Extract returned `[ORG]` for both tenant and landlord. Fixed with instructions that exclude role terms, fragment merging, and stable per-entity tokens: `[ORG_1]` and `[ORG_2]` remain distinct.

**Grounding on a whole document is noise.** Passing the lease as an "answer" produced sixteen claims, including "BASE RENT." and "not_a_claim" fragments. Fixed by extracting fields first, building four to eight operative claims, and probing the regulatory source for each claim's topic so only adjudicable claims are sent.

**The model cannot do arithmetic.** Asked whether four bays satisfy "two per 100 sqm" on 220 sqm, Verify answered *not stated*. The rule engine computes `ceil(220 ÷ 100 × 2) = 5` and reports a one-bay shortfall. That failure became the product's central design decision: models read, code counts.

**The Next.js frontend had no source.** Only a static export existed, so it could not be extended with pricing, billing or reports. We kept the API contract and rebuilt the client as a zero-build PWA served by FastAPI — one process, no toolchain, no CDN.

**Supabase tables existed without grants.** The first prototype's tables returned `42501` for both anon and service roles. The v2 schema creates namespaced `at_*` tables, grants the PostgREST roles explicitly, enables RLS, and the server falls back to SQLite with a visible reason if the schema has not been applied.

## Accomplishments we are proud of

- Five Clocked endpoints, all three groups, each output visibly changing the next step.
- A privacy design that preserves referential integrity and never stores the re-identification key.
- Deterministic arithmetic layered under model judgement, with the formula shown to the user.
- A real product surface — accounts, quotas, usage, plans, API keys, exports — not just a demo page.
- A measured cost per audit (31 credits, ~$0.009) that makes the pricing model defensible.
- 40 tests, a one-command run, and a fallback that keeps the demo alive without Supabase.

## What we learned

- Evidence beats prose. A verdict plus a quote is worth more than a better-written paragraph.
- Masking is not a preprocessing detail; done naively it destroys the relationships the audit depends on.
- The most valuable engineering decision was deciding what **not** to ask the model.
- Breadth is cheap to claim and expensive to do well: a sixth endpoint is only worth adding if it changes a downstream decision.

## What's next

- **Compare** two lease drafts and report which amendments introduce or cure a compliance issue — the natural next Clocked endpoint, and the third in the Verify group.
- **Fill** notice templates from extracted fields, so the remediation letter is generated with the same evidence.
- **Rerank** clauses by financial exposure to order the review queue.
- Jurisdiction rule packs (parking, use classes, signage, hours) as data, not code.
- Reviewer queue and firm-level roles for the Firm plan; SOC 2 readiness for Enterprise.

## Built with

`clocked-sdk` · Clocked API (`pii`, `injection`, `extract`, `grounding`, `decide`) · Python · FastAPI · Pydantic · httpx · Supabase (Postgres, Auth, RLS) · SQLite · vanilla JavaScript · CSS · Docker

## Try it

```bash
git clone https://github.com/pranpatel08-web/AuditTrail-AI.git
cd audittrail-ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # add CLOCKED_API_KEY (and Supabase keys if you have them)
python run.py               # http://127.0.0.1:8000
```

Click **Load sample** → **Run audit**. The sample contains a parking shortfall, an entertainment-licensing conflict and two documentation gaps.

Repository: **https://github.com/pranpatel08-web/AuditTrail-AI**
Demo video: **https://github.com/pranpatel08-web/AuditTrail-AI/releases/download/demo-v1/AuditTrail-AI-demo.webm**
Hosted demo: not deployed — the release video is the demo. Run locally with `python run.py`.

## Team

**[NAME]** — [role, GitHub handle, email]

---

### Submission checklist

- [ ] Repository public, history visible, no keys committed (`.env` is git-ignored)
- [ ] `README.md` links the demo video and hosted URL
- [ ] Demo video recorded from a clean start, under three minutes
- [ ] Entry form: all four judged awards selected
- [ ] "How you used Clocked" section pasted from above
- [ ] LinkedIn post published with `#ClockedChallenge` and the Clocked page tagged, if entering People's Choice
- [ ] Submitted before **10 Nov 2026, 11:59 p.m. ET**
