# Architecture

One process serves the API and the product UI. Five Clocked calls run sequentially; everything else is application logic that exists to make those calls trustworthy.

```
┌──────────────────────────── Browser (PWA, no build step) ───────────────────────────┐
│  Landing · Workspace · History · Report · Pricing · Billing · API keys · Method     │
│  Supabase Auth (email/password) ─► access token                                     │
└──────────────────────────────────────────┬──────────────────────────────────────────┘
                                           │  Authorization: Bearer <jwt>  or  X-API-Key
                                           ▼
┌───────────────────────────────────── FastAPI ───────────────────────────────────────┐
│  resolve_identity      verify JWT with Supabase / hash the API key; ignore user_id  │
│  billing.ensure_can_run plan quota from the persisted audit count                   │
│                                                                                     │
│  orchestrator.run_audit                                                             │
│    1 protect   clocked.pii        ─► entity spans                                  │
│       pseudonymise                ─► stable tokens + in-memory vault               │
│    2 guard     clocked.injection  ─► pass / BLOCK (fail closed)                    │
│    3 extract   clocked.extract    ─► 12 verbatim fields + spans                    │
│       claims.build                ─► 4–8 operative claims + numeric facts          │
│    4 verify    clocked.grounding  ─► verdict + evidence quote per claim            │
│       rules.evaluate              ─► deterministic arithmetic, formulas shown      │
│    5 decide    clocked.decide     ─► risk level, actions, review flag              │
│       policy.assess               ─► score, escalation, action list                │
│                                                                                     │
│  storage.create_audit  ─► Supabase Postgres (RLS)  or  SQLite fallback              │
│  reports.render_*      ─► HTML (print to PDF) · Markdown · JSON                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Request lifecycle

1. **Identity.** `Authorization: Bearer` is verified against `GET {SUPABASE_URL}/auth/v1/user` with the publishable key. An `X-API-Key` is SHA-256 hashed and looked up. If neither is present and `ALLOW_DEMO_MODE` is on, a fixed demo identity is used and the response says `identity.mode = "demo"`. A `user_id` in the body is ignored.
2. **Quota.** The caller's plan is read from `at_profiles` (or the SQLite equivalent); the audit count for the calendar month is compared to the plan allowance. Exhausted plans get `402` with the usage payload the UI needs to show an upgrade prompt.
3. **Protect.** The lease is sent to `clocked.pii` with ten entity kinds and instructions that exclude defined role terms. The response's spans are merged, deduplicated against regex backstops, turned into stable tokens, and applied right-to-left. The raw text is not forwarded anywhere else.
4. **Guard.** The masked text goes to `clocked.injection`. `dangerous`, `injection` or `malicious` stops the run; a blocked record is stored with the guard verdict and no lease fields.
5. **Extract.** The masked text goes to `clocked.extract` with twelve field definitions. The normaliser keeps value, start, end and confidence, and drops any field the model did not return.
6. **Claims.** `claims.build_claims` turns fields into operative claims, each tagged with a probe. Claims whose topic the source never mentions are kept for the report but not sent to Verify. Parking is rule-owned and never sent to Verify, because the model cannot do the arithmetic.
7. **Verify.** The source, the claims and a short factual answer go to `clocked.grounding`. The normaliser keeps verdict, probabilities, weight and the evidence quote with offsets.
8. **Rules.** `rules.evaluate` runs six or more deterministic checks over the lease and the source. Each returns status, severity, detail, formula and the source sentence.
9. **Decide.** A compact state (masked text, extracted fields, grounding verdicts, rule failures) goes to `clocked.decide` with four typed questions. Answers are normalised to `{value, probability}` / `{value, probabilities}` / `{value[], probabilities}`.
10. **Policy.** `policy.assess` scores the audit (contradictions, rule failures, unverifiable terms, missing fields, model probability), sets the level, escalates on hard failures, merges actions, and records the rationale.
11. **Persist and render.** The record (masked document, claims, rules, fields, risk, timings, measured credits) is stored against the verified user id. The re-identification vault is returned in the response only and never persisted.

## Trust boundaries

| Boundary | What crosses it | Control |
| --- | --- | --- |
| Browser → API | JWT, API key, lease text, source text | HTTPS in deployment, CSP, security headers, no raw PII in the stored record |
| API → Clocked | Masked lease, source, claims | Only masked text after step 1; no keys or vault in prompts |
| API → Supabase | JWT verification, server-side writes | Secret key server-side only; RLS on every table; queries filtered by `user_id` |
| Browser → Supabase Auth | Email, password | Direct to Supabase; the backend never sees the password |
| Report export | Masked audit record | Rendered server-side; HTML escaped; no vault |

## Data model

```
at_profiles(user_id pk → auth.users, email, plan, org_name, created_at)
at_audits(id pk, user_id → auth.users, created_at, title, status,
          risk_level, score, record jsonb)
at_api_keys(key_hash pk, user_id, label, prefix, created_at, last_used)
at_leads(id, email, company, note, created_at)          -- service role only
```

`record` holds the full audit: masked document, claims, rules, extracted fields, risk, step timings, measured credits. It never holds the vault, the raw document, or a provider key.

## Failure modes

| Failure | Behaviour | What the user sees |
| --- | --- | --- |
| `CLOCKED_API_KEY` missing | Fail closed (`FAIL_CLOSED=true`) | `503 clocked_not_configured`; the UI says the engine is offline |
| Clocked call fails | Sanitised `502` with the step name | "The pipeline stopped" + failing step; nothing is stored |
| Injection detected | Guard aborts before extract | Blocked audit with verdict and probability; routed to human review |
| Quota exhausted | `402` before any Clocked call | Upgrade prompt with remaining/limit |
| Supabase missing or schema absent | Fallback to SQLite; reason in `/health` | Header shows `engine live · sqlite` |
| Report export while logged out | Demo identity only sees its own audits | 404 for another user's id |
| Oversized input | Truncated to configured limits, flagged | Report notes truncation |

## Why the rule engine is separate

A language model can read "two parking bays per 100 square metres" and "220 square metres, four bays" and still answer *not stated*. Arithmetic is deterministic, testable and explainable; asking a model to do it adds variance without adding capability. The rule engine returns a formula (`ceil(220 ÷ 100 × 2) = 5`) that a reviewer can check in their head, and the policy layer treats a rule failure as a floor on risk: the model can raise the level, never lower it below a hard failure.

## Deployment

- Single container, `uvicorn` on `0.0.0.0:8000`, health check `/api/v1/health`.
- `Dockerfile` and `render.yaml` included; any container host works.
- Static UI is served by the same process, so there is no CORS surface in production and no separate frontend deploy.
- SQLite needs a persistent volume; Supabase needs no local state.
- `data/` is git-ignored; `.env` is git-ignored.

## Scaling notes

The pipeline is I/O-bound and synchronous per request. Five sequential calls at ~1 s each means a worker handles roughly one audit at a time; run 2–4 workers per CPU-bound instance, or move `run_audit` to a background queue for firm-scale volume. Clocked concurrency is the binding constraint (4 concurrent requests on the challenge grant, 8 on Production). Audits are idempotent per request id; retries are safe because each call carries an SDK-generated idempotency key.
