"""Request identity.

Two modes, both explicit:

* **Authenticated** - the browser holds a Supabase session and sends the access
  token. We verify it against Supabase and use `auth.uid()` as the owner. A
  client-supplied `user_id` is never trusted.
* **Demo** - when `ALLOW_DEMO_MODE` is on, unauthenticated requests act as a
  single fixed demo identity so judges can try the product without signing up.
  The API response says which mode was used, so it can never be mistaken for a
  multi-tenant session.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request, status

from .config import Settings, get_settings
from .storage import get_store

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL_SECONDS = 60


@dataclass
class Identity:
    user_id: str
    email: str | None
    mode: str  # "supabase" | "demo"
    token: str | None = None


def _verify_with_supabase(token: str, settings: Settings) -> dict | None:
    cached = _CACHE.get(token)
    now = time.time()
    if cached and cached[0] > now:
        return cached[1]
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except Exception:
        return None
    if response.status_code != 200:
        return None
    user = response.json()
    _CACHE[token] = (now + _TTL_SECONDS, user)
    return user


def resolve_identity(request: Request, settings: Settings | None = None) -> Identity:
    settings = settings or get_settings()

    api_key = request.headers.get("x-api-key", "").strip()
    if api_key:
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        user_id = get_store().find_api_key(digest)
        if user_id:
            return Identity(user_id=user_id, email=None, mode="api")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
        if token and settings.supabase_ready:
            user = _verify_with_supabase(token, settings)
            if user and user.get("id"):
                return Identity(user_id=user["id"], email=user.get("email"), mode="supabase", token=token)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid. Sign in again.",
            )
    if settings.demo_mode:
        return Identity(user_id=settings.demo_user_id, email="demo@audittrail.ai", mode="demo")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")


def current_identity(request: Request) -> Identity:
    """FastAPI dependency wrapper (keeps `settings` out of the signature)."""
    return resolve_identity(request)
