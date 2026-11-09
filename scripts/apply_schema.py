"""Apply supabase/schema.sql to a Supabase Postgres database.

The dashboard SQL editor is the simplest route; this script exists for people
who would rather run one command with the connection string from
Dashboard -> Connect.

    pip install -r requirements-dev.txt
    python scripts/apply_schema.py --db-url "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"

Or put SUPABASE_DB_URL in .env and run it with no arguments.

The script is idempotent: schema.sql uses `create table if not exists`,
`drop policy if exists`, and `on conflict`, so it is safe to re-run.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv, find_dotenv  # noqa: E402

load_dotenv(find_dotenv())


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the AuditTrail AI schema to Supabase")
    parser.add_argument("--db-url", default=os.getenv("SUPABASE_DB_URL", ""), help="Postgres connection string")
    parser.add_argument("--file", default=str(ROOT / "supabase" / "schema.sql"))
    args = parser.parse_args()

    if not args.db_url:
        print("No connection string.")
        print("Either run supabase/schema.sql in the Supabase SQL editor, or pass:")
        print('  python scripts/apply_schema.py --db-url "postgresql://postgres.<ref>:<password>@...pooler.supabase.com:5432/postgres"')
        return 2

    try:
        import psycopg
    except ImportError:
        print("psycopg is not installed. Run: pip install -r requirements-dev.txt")
        return 2

    sql = Path(args.file).read_text(encoding="utf-8")
    print(f"Applying {args.file} ...")
    try:
        with psycopg.connect(args.db_url, connect_timeout=20, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "select tablename from pg_tables where schemaname='public' "
                    "and tablename like 'at\\_%' order by 1"
                )
                tables = [row[0] for row in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001 - surface a readable message
        print(f"FAILED: {exc.__class__.__name__}: {exc}")
        return 1

    print("Created/verified:", ", ".join(tables) or "none")
    if len(tables) < 4:
        print("WARN: expected at_audits, at_profiles, at_api_keys, at_leads")
        return 1
    print("OK — restart the server and check GET /api/v1/health for \"backend\": \"supabase\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
