"""Persistence with two interchangeable backends.

Supabase (Postgres + RLS) is the production store. A local SQLite store keeps
the product fully usable when Supabase is not configured - useful for offline
demos, air-gapped legal teams, and CI. Both implement the same small interface,
so the API layer never branches on storage.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote
from pathlib import Path
from typing import Any, Protocol

import httpx

from .config import Settings, get_settings

logger = logging.getLogger("audittrail.storage")

SQLITE_SCHEMA = """
create table if not exists audits (
    id text primary key,
    user_id text not null,
    created_at text not null,
    title text not null,
    status text not null,
    risk_level text,
    score integer,
    record text not null
);
create index if not exists audits_user_idx on audits (user_id, created_at desc);
create table if not exists profiles (
    user_id text primary key,
    email text,
    plan text not null default 'free',
    org_name text,
    created_at text not null
);
create table if not exists leads (
    id integer primary key autoincrement,
    email text not null,
    company text,
    note text,
    created_at text not null
);
create table if not exists api_keys (
    key_hash text primary key,
    user_id text not null,
    label text,
    prefix text,
    created_at text not null,
    last_used text
);
create index if not exists api_keys_user_idx on api_keys (user_id);
"""


class Store(Protocol):
    name: str

    def create_audit(self, user_id: str, record: dict[str, Any]) -> str: ...
    def list_audits(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]: ...
    def get_audit(self, user_id: str, audit_id: str) -> dict[str, Any] | None: ...
    def count_audits_since(self, user_id: str, since_iso: str) -> int: ...
    def get_profile(self, user_id: str) -> dict[str, Any]: ...
    def upsert_profile(self, user_id: str, **fields: Any) -> dict[str, Any]: ...
    def add_lead(self, email: str, company: str | None, note: str | None) -> None: ...
    def create_api_key(self, user_id: str, key_hash: str, label: str | None, prefix: str) -> None: ...
    def list_api_keys(self, user_id: str) -> list[dict[str, Any]]: ...
    def find_api_key(self, key_hash: str) -> str | None: ...
    def health(self) -> dict[str, Any]: ...


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    risk = record.get("risk") or {}
    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "created_at": record.get("created_at"),
        "status": record.get("status"),
        "risk_level": risk.get("risk_level"),
        "score": risk.get("score"),
        "contradicted": (risk.get("claim_stats") or {}).get("contradicted", 0),
        "rule_failures": (risk.get("rule_stats") or {}).get("fail", 0),
        "total_ms": (record.get("timings") or {}).get("total_ms"),
    }


class SQLiteStore:
    name = "sqlite"

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(SQLITE_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def create_audit(self, user_id: str, record: dict[str, Any]) -> str:
        risk = record.get("risk") or {}
        with self._lock, self._connect() as conn:
            conn.execute(
                "insert or replace into audits (id,user_id,created_at,title,status,risk_level,score,record)"
                " values (?,?,?,?,?,?,?,?)",
                (
                    record["id"],
                    user_id,
                    record["created_at"],
                    record.get("title") or "Untitled",
                    record.get("status") or "success",
                    risk.get("risk_level"),
                    risk.get("score"),
                    json.dumps(record),
                ),
            )
        return record["id"]

    def list_audits(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select record from audits where user_id = ? order by created_at desc limit ?",
                (user_id, limit),
            ).fetchall()
        return [_summary(json.loads(row["record"])) for row in rows]

    def get_audit(self, user_id: str, audit_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select record from audits where user_id = ? and id = ?", (user_id, audit_id)
            ).fetchone()
        return json.loads(row["record"]) if row else None

    def count_audits_since(self, user_id: str, since_iso: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "select count(*) as n from audits where user_id = ? and created_at >= ?",
                (user_id, since_iso),
            ).fetchone()
        return int(row["n"])

    def get_profile(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from profiles where user_id = ?", (user_id,)).fetchone()
        if row:
            return dict(row)
        return self.upsert_profile(user_id)

    def upsert_profile(self, user_id: str, **fields: Any) -> dict[str, Any]:
        current = None
        with self._connect() as conn:
            row = conn.execute("select * from profiles where user_id = ?", (user_id,)).fetchone()
            current = dict(row) if row else {
                "user_id": user_id,
                "email": None,
                "plan": "free",
                "org_name": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        current.update({k: v for k, v in fields.items() if v is not None})
        with self._lock, self._connect() as conn:
            conn.execute(
                "insert into profiles (user_id,email,plan,org_name,created_at) values (?,?,?,?,?)"
                " on conflict(user_id) do update set email=excluded.email, plan=excluded.plan,"
                " org_name=excluded.org_name",
                (
                    current["user_id"],
                    current.get("email"),
                    current.get("plan") or "free",
                    current.get("org_name"),
                    current["created_at"],
                ),
            )
        return current

    def add_lead(self, email: str, company: str | None, note: str | None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "insert into leads (email,company,note,created_at) values (?,?,?,?)",
                (email, company, note, datetime.now(timezone.utc).isoformat()),
            )

    def create_api_key(self, user_id: str, key_hash: str, label: str | None, prefix: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "insert into api_keys (key_hash,user_id,label,prefix,created_at) values (?,?,?,?,?)",
                (key_hash, user_id, label, prefix, datetime.now(timezone.utc).isoformat()),
            )

    def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select prefix,label,created_at,last_used from api_keys where user_id = ? order by created_at desc",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def find_api_key(self, key_hash: str) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("select user_id from api_keys where key_hash = ?", (key_hash,)).fetchone()
            if row:
                conn.execute(
                    "update api_keys set last_used = ? where key_hash = ?",
                    (datetime.now(timezone.utc).isoformat(), key_hash),
                )
        return row["user_id"] if row else None

    def health(self) -> dict[str, Any]:
        return {"backend": self.name, "ready": True, "detail": f"SQLite at {self.path}"}


class SupabaseStore:
    name = "supabase"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base = settings.supabase_url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": settings.supabase_secret_key,
            "Authorization": f"Bearer {settings.supabase_secret_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        with httpx.Client(timeout=20) as client:
            response = client.request(method, f"{self.base}/{path}", headers=headers, **kwargs)
        return response

    def ready(self) -> tuple[bool, str]:
        try:
            response = self._request("GET", "at_audits?select=id&limit=1")
        except Exception as exc:  # pragma: no cover - network
            return False, f"unreachable: {exc.__class__.__name__}"
        if response.status_code == 200:
            return True, "ok"
        return False, f"schema not initialised ({response.status_code}: {response.text[:160]})"

    def create_audit(self, user_id: str, record: dict[str, Any]) -> str:
        risk = record.get("risk") or {}
        row = {
            "id": record["id"],
            "user_id": user_id,
            "created_at": record["created_at"],
            "title": record.get("title") or "Untitled",
            "status": record.get("status") or "success",
            "risk_level": risk.get("risk_level"),
            "score": risk.get("score"),
            "record": record,
        }
        response = self._request("POST", "at_audits", json=row, headers={**self.headers, "Prefer": "return=minimal"})
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase insert failed: {response.status_code} {response.text[:200]}")
        return record["id"]

    def list_audits(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"at_audits?user_id=eq.{user_id}&select=record&order=created_at.desc&limit={int(limit)}",
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase list failed: {response.status_code} {response.text[:200]}")
        return [_summary(row["record"]) for row in response.json()]

    def get_audit(self, user_id: str, audit_id: str) -> dict[str, Any] | None:
        response = self._request(
            "GET", f"at_audits?user_id=eq.{user_id}&id=eq.{audit_id}&select=record&limit=1"
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase get failed: {response.status_code} {response.text[:200]}")
        rows = response.json()
        return rows[0]["record"] if rows else None

    def count_audits_since(self, user_id: str, since_iso: str) -> int:
        response = self._request(
            "GET",
            f"at_audits?user_id=eq.{user_id}&created_at=gte.{quote(since_iso, safe='')}&select=id",
            headers={**self.headers, "Prefer": "count=exact", "Range": "0-0"},
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"Supabase count failed: {response.status_code} {response.text[:200]}"
            )
        count_range = response.headers.get("content-range", "0-0/0")
        return int(count_range.split("/")[-1] or 0)

    def get_profile(self, user_id: str) -> dict[str, Any]:
        response = self._request("GET", f"at_profiles?user_id=eq.{user_id}&select=*&limit=1")
        rows = response.json() if response.status_code < 300 else []
        if rows:
            return rows[0]
        return self.upsert_profile(user_id)

    def upsert_profile(self, user_id: str, **fields: Any) -> dict[str, Any]:
        payload = {"user_id": user_id, **{k: v for k, v in fields.items() if v is not None}}
        response = self._request(
            "POST",
            "at_profiles?on_conflict=user_id",
            json=payload,
            headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"},
        )
        if response.status_code >= 300:
            logger.warning("Profile upsert failed: %s", response.text[:200])
            return {"user_id": user_id, "plan": "free", **payload}
        rows = response.json()
        return rows[0] if rows else {"user_id": user_id, "plan": "free", **payload}

    def add_lead(self, email: str, company: str | None, note: str | None) -> None:
        self._request(
            "POST",
            "at_leads",
            json={"email": email, "company": company, "note": note},
            headers={**self.headers, "Prefer": "return=minimal"},
        )

    def create_api_key(self, user_id: str, key_hash: str, label: str | None, prefix: str) -> None:
        response = self._request(
            "POST",
            "at_api_keys",
            json={"key_hash": key_hash, "user_id": user_id, "label": label, "prefix": prefix},
            headers={**self.headers, "Prefer": "return=minimal"},
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase key insert failed: {response.status_code} {response.text[:160]}")

    def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"at_api_keys?user_id=eq.{user_id}&select=prefix,label,created_at,last_used&order=created_at.desc",
        )
        return response.json() if response.status_code < 300 else []

    def find_api_key(self, key_hash: str) -> str | None:
        response = self._request("GET", f"at_api_keys?key_hash=eq.{key_hash}&select=user_id&limit=1")
        rows = response.json() if response.status_code < 300 else []
        if not rows:
            return None
        self._request(
            "PATCH",
            f"at_api_keys?key_hash=eq.{key_hash}",
            json={"last_used": datetime.now(timezone.utc).isoformat()},
            headers={**self.headers, "Prefer": "return=minimal"},
        )
        return rows[0]["user_id"]

    def health(self) -> dict[str, Any]:
        ready, detail = self.ready()
        return {"backend": self.name, "ready": ready, "detail": detail}


class StoreRouter:
    """Chooses Supabase when it is usable, otherwise SQLite."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.sqlite = SQLiteStore(settings.database_path)
        self.supabase: SupabaseStore | None = None
        self.active: Store = self.sqlite
        self._last_probe = 0.0
        self._last_reason = "not checked"
        self._resolve()

    def _resolve(self) -> None:
        choice = self.settings.storage_backend
        if choice == "sqlite" or not self.settings.supabase_ready:
            self.active = self.sqlite
            self._last_reason = "sqlite selected"
            return
        candidate = SupabaseStore(self.settings)
        ready, detail = candidate.ready()
        self._last_reason = "ok" if ready else detail
        if ready:
            self.supabase = candidate
            self.active = candidate
        else:
            logger.warning("Supabase configured but not usable: %s", detail)
            self.active = self.sqlite

    def refresh(self) -> None:
        self._resolve()

    def _probe_for_upgrade(self) -> None:
        """Promote SQLite → Supabase once the schema becomes available.

        The schema is applied in the SQL editor, usually while the server is
        already running. Probing here (throttled) means /health flips to
        Supabase without a restart or a redeploy.
        """
        if self.active is not self.sqlite or not self.settings.supabase_ready:
            return
        now = time.time()
        if now - self._last_probe < 15:
            return
        self._last_probe = now
        candidate = self.supabase or SupabaseStore(self.settings)
        ready, reason = candidate.ready()
        self._last_reason = "ok" if ready else reason
        if ready:
            self.supabase = candidate
            self.active = candidate
            logger.info("Supabase schema detected; switched active storage to Supabase")

    def status(self) -> dict[str, Any]:
        self._probe_for_upgrade()
        detail = self.active.health()
        if self.active is self.sqlite and self.settings.supabase_ready:
            detail["supabase_reason"] = self._last_reason
        return detail

    # delegate ------------------------------------------------------------
    def create_audit(self, user_id: str, record: dict[str, Any]) -> str:
        return self.active.create_audit(user_id, record)

    def list_audits(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.active.list_audits(user_id, limit)

    def get_audit(self, user_id: str, audit_id: str) -> dict[str, Any] | None:
        return self.active.get_audit(user_id, audit_id)

    def count_audits_since(self, user_id: str, since_iso: str) -> int:
        return self.active.count_audits_since(user_id, since_iso)

    def get_profile(self, user_id: str) -> dict[str, Any]:
        return self.active.get_profile(user_id)

    def upsert_profile(self, user_id: str, **fields: Any) -> dict[str, Any]:
        return self.active.upsert_profile(user_id, **fields)

    def add_lead(self, email: str, company: str | None, note: str | None) -> None:
        return self.active.add_lead(email, company, note)

    def create_api_key(self, user_id: str, key_hash: str, label: str | None, prefix: str) -> None:
        return self.active.create_api_key(user_id, key_hash, label, prefix)

    def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        return self.active.list_api_keys(user_id)

    def find_api_key(self, key_hash: str) -> str | None:
        return self.active.find_api_key(key_hash)


_router: StoreRouter | None = None


def get_store() -> StoreRouter:
    global _router
    if _router is None:
        _router = StoreRouter(get_settings())
    return _router
