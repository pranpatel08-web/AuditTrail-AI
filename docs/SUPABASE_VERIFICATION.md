# Supabase verification

Recorded on **10 November 2026** against project `ttdogpagtsabxldkhsbh` (Postgres 17, `us-east-1`), after applying [`supabase/schema.sql`](../supabase/schema.sql) through the Management API.

## Schema

Applied successfully; 4 tables and 7 policies created:

| Table | Policies |
| --- | --- |
| `at_audits` | read own, insert own, delete own |
| `at_profiles` | read own, insert own, update own |
| `at_api_keys` | read own |
| `at_leads` | service role only (no authenticated policy) |

Grants were applied explicitly to `authenticated` and `service_role`; `anon` is denied.

## Runtime switch

`GET /api/v1/health`:

```json
{
  "status": "ok",
  "clocked_live": true,
  "storage": { "backend": "supabase", "ready": true, "detail": "ok" },
  "pipeline": ["protect", "guard", "extract", "verify", "decide"]
}
```

The server auto-detects the schema on a 15-second probe, so the switch happened without a restart. The header in the UI shows `engine live · supabase`.

## Live audit written to Postgres

A real five-step audit of the bundled lease completed in ~11 s and persisted:

| Field | Value |
| --- | --- |
| `risk_level` | `HIGH` |
| `score` | `100` |
| `status` | `success` |
| `title` | 412 Harbor Street — Verde Coffee Roasters |
| rows in `at_audits` | 2 (from two verification runs) |

The `at_profiles` row for the demo account was created automatically by the `at_handle_new_user` trigger.

## Tenant isolation (RLS)

A second auth user (`isolation-test@audittrail.ai`) was created and signed in with the publishable key:

```
second user sees: 200 []
service role sees rows: 1
```

The second user sees an empty set even though the table contains rows. Anonymous reads with the publishable key are rejected with `42501`. This is the RLS claim demonstrated, not asserted.

## Demo mode on a Supabase deployment

Demo requests use a real auth account (`demo@audittrail.ai`) that the server finds or creates via the Admin API and caches for an hour. Without it, an unauthenticated demo audit would violate the `user_id` foreign key on insert. The account is bounded by the normal plan quota, so a public demo cannot burn unlimited credits.

## Reproduce

```bash
# 1. apply the schema (SQL editor, or scripts/apply_schema.py with a DB URL)
# 2. run the server
python run.py

# 3. check the backend
curl http://127.0.0.1:8000/api/v1/health

# 4. run a real audit and confirm the row
python scripts/smoke.py
```

```sql
select id, title, risk_level, score, created_at
from public.at_audits order by created_at desc limit 5;
```

## Notes

- Raw tenant identifiers are not in these rows: the stored `record` contains only the masked document.
- The re-identification key is returned to the caller and never written to `at_audits`.
- The two personal access tokens used for setup were provided by the owner and should be revoked after use.
