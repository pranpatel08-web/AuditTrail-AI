"""HTTP API.

Every route is scoped to the authenticated identity. The only trust boundary is
`resolve_identity`: a `user_id` in the request body is ignored, so one tenant
cannot read another tenant's audits by guessing an id.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from . import billing, reports
from .auth import Identity, resolve_identity
from .clocked import ClockedGateway, PipelineError
from .config import get_settings
from .orchestrator import run_audit
from .storage import get_store

logger = logging.getLogger("audittrail.api")
router = APIRouter(prefix="/api/v1")
SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class AuditRequest(BaseModel):
    document_text: str = Field(..., min_length=20, description="Lease / deed text to audit")
    compliance_rules: str = Field(..., min_length=20, description="Regional zoning or regulatory source")
    title: str = Field("", max_length=140)
    include_key: bool = Field(True, description="Return the one-time re-identification key")


class LeadRequest(BaseModel):
    email: str = Field(..., max_length=200)
    company: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=1000)


class PlanRequest(BaseModel):
    plan: str


class CheckoutRequest(BaseModel):
    plan: str
    return_url: str = "http://localhost:8000/"


def _identity(request: Request) -> Identity:
    return resolve_identity(request)


@router.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    store = get_store()
    return {
        "status": "ok",
        "version": settings.version,
        "clocked_live": settings.clocked_ready,
        "storage": store.status(),
        "pipeline": ["protect", "guard", "extract", "verify", "decide"],
        "billing": "live" if settings.billing_live else "sandbox",
    }


@router.get("/config")
def public_config() -> dict[str, Any]:
    settings = get_settings()
    store = get_store()
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "supabase_url": settings.supabase_url or None,
        "supabase_key": settings.supabase_publishable_key or None,
        "demo_mode": settings.demo_mode,
        "storage": store.status(),
        "billing_live": settings.billing_live,
        "plans": [billing.PLANS[p] for p in billing.PLAN_ORDER],
    }


@router.get("/samples")
def samples() -> dict[str, str]:
    lease = (SAMPLES / "lease_excerpt.txt").read_text(encoding="utf-8")
    zoning = (SAMPLES / "zoning_rules.txt").read_text(encoding="utf-8")
    return {"lease": lease, "zoning": zoning}


@router.post("/audit/process")
def process_audit(payload: AuditRequest, identity: Identity = Depends(_identity)) -> dict[str, Any]:
    settings = get_settings()
    store = get_store()
    profile = store.get_profile(identity.user_id)
    plan = profile.get("plan") or "free"

    try:
        usage = billing.ensure_can_run(store, identity.user_id, plan)
    except billing.QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "quota_exceeded",
                "message": str(exc),
                "usage": billing.usage_for(store, identity.user_id, plan),
            },
        )

    try:
        run = run_audit(
            lease_text=payload.document_text,
            rules_text=payload.compliance_rules,
            title=payload.title,
            user_id=identity.user_id,
            gateway=ClockedGateway(),
            settings=settings,
        )
    except PipelineError as exc:
        logger.warning("Audit failed at step %s (%s)", exc.step, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "clocked_failure",
                "step": exc.step,
                "message": str(exc),
                "retryable": exc.retryable,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    record = run.record
    store.create_audit(identity.user_id, record)

    response: dict[str, Any] = {
        "status": record["status"],
        "audit": record,
        "identity": {"mode": identity.mode},
        "usage": billing.usage_for(store, identity.user_id, plan),
    }
    if payload.include_key:
        response["reidentification_key"] = run.vault
        response["key_notice"] = (
            "This is the only time the key is returned. It is not stored by AuditTrail."
        )
    return response


@router.get("/audits")
def list_audits(identity: Identity = Depends(_identity), limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    return {"audits": get_store().list_audits(identity.user_id, limit)}


def _owned_audit(audit_id: str, identity: Identity) -> dict[str, Any]:
    record = get_store().get_audit(identity.user_id, audit_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audit not found.")
    return record


@router.get("/audits/{audit_id}")
def get_audit(audit_id: str, identity: Identity = Depends(_identity)) -> dict[str, Any]:
    return {"audit": _owned_audit(audit_id, identity)}


def _brand(identity: Identity) -> str | None:
    store = get_store()
    profile = store.get_profile(identity.user_id)
    plan = profile.get("plan") or "free"
    org = profile.get("org_name")
    if billing.PLANS.get(plan, {}).get("white_label") and org:
        return org
    if plan == "free":
        return "AuditTrail AI — review copy"
    return None


@router.get("/audits/{audit_id}/report.md")
def report_markdown(audit_id: str, identity: Identity = Depends(_identity)) -> Response:
    record = _owned_audit(audit_id, identity)
    body = reports.render_markdown(record, org_name=_brand(identity))
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="audittrail-{audit_id[:8]}.md"'},
    )


@router.get("/audits/{audit_id}/report.html")
def report_html(audit_id: str, identity: Identity = Depends(_identity), download: int = 0) -> Response:
    record = _owned_audit(audit_id, identity)
    body = reports.render_html(record, org_name=_brand(identity))
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="audittrail-{audit_id[:8]}.html"'
    return Response(content=body, media_type="text/html; charset=utf-8", headers=headers)


@router.get("/audits/{audit_id}/report.json")
def report_json(audit_id: str, identity: Identity = Depends(_identity)) -> Response:
    record = _owned_audit(audit_id, identity)
    return Response(
        content=reports.render_json(record),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="audittrail-{audit_id[:8]}.json"'},
    )


@router.get("/billing/plans")
def plans() -> dict[str, Any]:
    return {"plans": [billing.PLANS[p] for p in billing.PLAN_ORDER], "overage_price": billing.OVERAGE_PRICE}


@router.get("/billing/usage")
def usage(identity: Identity = Depends(_identity)) -> dict[str, Any]:
    store = get_store()
    profile = store.get_profile(identity.user_id)
    return billing.usage_for(store, identity.user_id, profile.get("plan") or "free")


@router.post("/billing/checkout")
def checkout(payload: CheckoutRequest, request: Request, identity: Identity = Depends(_identity)) -> dict[str, Any]:
    settings = get_settings()
    profile = get_store().get_profile(identity.user_id)
    result = billing.create_checkout(
        payload.plan,
        user_id=identity.user_id,
        email=identity.email or profile.get("email"),
        return_url=payload.return_url or str(request.base_url).rstrip("/"),
        settings=settings,
    )
    return result


@router.post("/billing/plan")
def change_plan(payload: PlanRequest, identity: Identity = Depends(_identity)) -> dict[str, Any]:
    settings = get_settings()
    if settings.billing_live:
        raise HTTPException(
            status_code=409,
            detail="Live billing is enabled: change plans through Stripe Checkout.",
        )
    if payload.plan not in billing.PLANS:
        raise HTTPException(status_code=422, detail="Unknown plan.")
    profile = get_store().upsert_profile(identity.user_id, plan=payload.plan)
    return {"plan": profile.get("plan"), "mode": "sandbox"}


@router.post("/profile")
def update_profile(payload: dict[str, Any], identity: Identity = Depends(_identity)) -> dict[str, Any]:
    org = str(payload.get("org_name") or "").strip()[:120]
    profile = get_store().upsert_profile(identity.user_id, org_name=org or None, email=identity.email)
    return {"profile": profile}


@router.post("/leads")
def create_lead(payload: LeadRequest) -> dict[str, str]:
    if "@" not in payload.email:
        raise HTTPException(status_code=422, detail="A valid email is required.")
    get_store().add_lead(payload.email.strip(), payload.company, payload.note)
    return {"status": "recorded"}
