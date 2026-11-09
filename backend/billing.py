"""Plans, entitlements, usage metering and checkout.

Metering is real: every audit is persisted and counted against the plan's
monthly allowance. Checkout runs live against Stripe when keys are configured,
and in an explicitly-labelled sandbox otherwise, so the product is honest about
which mode it is in.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings, get_settings
from .storage import StoreRouter


class QuotaExceeded(RuntimeError):
    def __init__(self, plan: str, limit: int):
        super().__init__(f"The {plan} plan allows {limit} audits per month.")
        self.plan = plan
        self.limit = limit


PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Review",
        "price_monthly": 0,
        "audits_per_month": 3,
        "seats": 1,
        "export": False,
        "white_label": False,
        "api_access": False,
        "tagline": "Try a live audit on a real lease.",
        "features": [
            "3 audits per month",
            "Full claim-by-claim evidence report",
            "PII pseudonymisation with re-identification key",
            "Audit history for 30 days",
        ],
    },
    "pro": {
        "id": "pro",
        "name": "Solo",
        "price_monthly": 49,
        "audits_per_month": 100,
        "seats": 1,
        "export": True,
        "white_label": False,
        "api_access": True,
        "tagline": "For brokers and solo counsel closing deals weekly.",
        "features": [
            "100 audits per month",
            "Print-ready PDF, Markdown and JSON export",
            "API access with your own key",
            "Unlimited audit history",
            "Email support, 1 business day",
        ],
    },
    "firm": {
        "id": "firm",
        "name": "Firm",
        "price_monthly": 199,
        "audits_per_month": 500,
        "seats": 5,
        "export": True,
        "white_label": True,
        "api_access": True,
        "tagline": "For boutique firms running diligence at volume.",
        "features": [
            "500 audits per month, 5 seats",
            "White-label reports with your firm's name",
            "Shared audit history and reviewer queue",
            "Priority processing",
            "Onboarding and template library",
        ],
    },
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise",
        "price_monthly": None,
        "audits_per_month": None,
        "seats": None,
        "export": True,
        "white_label": True,
        "api_access": True,
        "tagline": "For institutions that cannot send documents to a shared cloud.",
        "features": [
            "Unlimited audits and seats",
            "On-premise or private VPC deployment",
            "SSO / SAML and audit-log export",
            "Custom rule packs per jurisdiction",
            "Named compliance engineer",
        ],
    },
}

PLAN_ORDER = ["free", "pro", "firm", "enterprise"]
OVERAGE_PRICE = 2.0  # USD per audit beyond the allowance


def month_bounds() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


def month_start_iso() -> str:
    return month_bounds()[0]


def usage_for(store: StoreRouter, user_id: str, plan: str) -> dict[str, Any]:
    definition = PLANS.get(plan, PLANS["free"])
    limit = definition["audits_per_month"]
    used = store.count_audits_since(user_id, month_start_iso())
    remaining = None if limit is None else max(0, limit - used)
    start, end = month_bounds()
    return {
        "plan": definition["id"],
        "plan_name": definition["name"],
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "percent": None if not limit else min(100, round(used / limit * 100)),
        "period_start": start,
        "period_end": end,
        "overage_price": OVERAGE_PRICE,
    }


def ensure_can_run(store: StoreRouter, user_id: str, plan: str) -> dict[str, Any]:
    usage = usage_for(store, user_id, plan)
    if usage["limit"] is not None and usage["used"] >= usage["limit"]:
        raise QuotaExceeded(plan, usage["limit"])
    return usage


def create_checkout(
    plan: str,
    *,
    user_id: str,
    email: str | None,
    return_url: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if plan not in PLANS or plan in {"free", "enterprise"}:
        return {
            "mode": "contact",
            "url": "mailto:sales@audittrail.ai?subject=AuditTrail%20Enterprise",
            "message": "Enterprise deployments are scoped with our team.",
        }

    price_id = settings.stripe_price_pro if plan == "pro" else settings.stripe_price_firm
    if not (settings.billing_live and price_id):
        return {
            "mode": "sandbox",
            "url": None,
            "message": (
                "Billing sandbox: plan changes are instant and no card is charged. "
                "Add STRIPE_SECRET_KEY and price IDs to enable live checkout."
            ),
        }

    payload = {
        "mode": "subscription",
        "success_url": f"{return_url}?checkout=success&plan={plan}",
        "cancel_url": f"{return_url}?checkout=cancelled",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "client_reference_id": user_id,
        "allow_promotion_codes": "true",
    }
    if email:
        payload["customer_email"] = email
    with httpx.Client(timeout=20) as client:
        response = client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=payload,
            auth=(settings.stripe_secret_key, ""),
        )
    if response.status_code >= 300:
        return {
            "mode": "error",
            "url": None,
            "message": "Stripe rejected the checkout request. Check the price IDs and secret key.",
        }
    session = response.json()
    return {"mode": "live", "url": session.get("url"), "message": "Redirecting to Stripe Checkout."}

