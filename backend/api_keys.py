"""API key issuance.

Paid plans include machine access. Keys are shown once, stored only as a
SHA-256 digest, and authenticate the same endpoints the browser session uses.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .auth import Identity, current_identity
from .billing import PLANS
from .storage import get_store

router = APIRouter(prefix="/api/v1/api-keys")


class KeyRequest(BaseModel):
    label: str | None = Field(None, max_length=80)


@router.get("")
def list_keys(identity: Identity = Depends(current_identity)) -> dict[str, Any]:
    store = get_store()
    plan = store.get_profile(identity.user_id).get("plan") or "free"
    return {
        "api_access": bool(PLANS.get(plan, {}).get("api_access")),
        "plan": plan,
        "keys": store.list_api_keys(identity.user_id),
        "usage": "Send X-API-Key: at_â€¦ with the same /api/v1 routes.",
    }


@router.post("")
def create_key(payload: KeyRequest, identity: Identity = Depends(current_identity)) -> dict[str, Any]:
    store = get_store()
    plan = store.get_profile(identity.user_id).get("plan") or "free"
    if not PLANS.get(plan, {}).get("api_access"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "plan_required",
                "message": "API access is available on the Solo and Firm plans.",
                "plan": plan,
            },
        )
    raw = "at_" + secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    store.create_api_key(identity.user_id, digest, payload.label, raw[:10])
    return {
        "key": raw,
        "prefix": raw[:10],
        "notice": "Copy this key now. It is stored as a hash and cannot be shown again.",
    }

