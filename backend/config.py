"""Runtime configuration for AuditTrail AI.

All values come from the environment (.env in the project root). Values are
stripped of accidental quotes so both `KEY=value` and `KEY="value"` work.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default) or default
    return value.strip().strip('"').strip("'")


def _flag(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "AuditTrail AI"
    version: str = "2.0.0"
    environment: str = field(default_factory=lambda: _env("APP_ENV", "development"))

    # Clocked
    clocked_api_key: str = field(default_factory=lambda: _env("CLOCKED_API_KEY"))
    clocked_api_url: str = field(
        default_factory=lambda: _env("CLOCKED_API_URL", "https://clocked.rezolve.ai/clocked")
    )
    clocked_timeout: float = field(default_factory=lambda: float(_env("CLOCKED_TIMEOUT", "90")))
    fail_closed: bool = field(default_factory=lambda: _flag("FAIL_CLOSED", True))

    # Supabase
    supabase_url: str = field(default_factory=lambda: _env("SUPABASE_URL"))
    supabase_secret_key: str = field(
        default_factory=lambda: _env("SUPABASE_SECRET_KEY") or _env("SUPABASE_SERVICE_ROLE_KEY")
    )
    supabase_publishable_key: str = field(
        default_factory=lambda: _env("SUPABASE_PUBLISHABLE_KEY") or _env("SUPABASE_ANON_KEY")
    )
    supabase_schema_ready: bool = field(default_factory=lambda: _flag("SUPABASE_SCHEMA_READY", False))

    # Storage
    database_path: Path = field(
        default_factory=lambda: Path(_env("DATABASE_PATH", str(ROOT / "data" / "audittrail.db")))
    )
    storage_backend: str = field(default_factory=lambda: _env("STORAGE_BACKEND", "auto").lower())

    # Product
    demo_mode: bool = field(default_factory=lambda: _flag("ALLOW_DEMO_MODE", True))
    demo_user_id: str = field(
        default_factory=lambda: _env("DEMO_USER_ID", "00000000-0000-4000-8000-000000000001")
    )
    max_lease_chars: int = field(default_factory=lambda: int(_env("MAX_LEASE_CHARS", "60000")))
    max_rules_chars: int = field(default_factory=lambda: int(_env("MAX_RULES_CHARS", "120000")))

    # Billing (optional; the product runs in sandbox mode without it)
    stripe_secret_key: str = field(default_factory=lambda: _env("STRIPE_SECRET_KEY"))
    stripe_price_pro: str = field(default_factory=lambda: _env("STRIPE_PRICE_PRO"))
    stripe_price_firm: str = field(default_factory=lambda: _env("STRIPE_PRICE_FIRM"))
    billing_portal_url: str = field(default_factory=lambda: _env("BILLING_PORTAL_URL"))

    @property
    def clocked_ready(self) -> bool:
        return bool(self.clocked_api_key)

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

    @property
    def billing_live(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_pro)


@lru_cache
def get_settings() -> Settings:
    return Settings()
