"""The application's risk policy.

Clocked Decide returns calibrated probabilities. This module turns them, plus
the deterministic rule findings, into the decision the product actually acts on:
a risk level, a 0-100 score, a remediation checklist, and whether a human must
sign off. Policy lives in application code, not in a prompt, so it is testable
and cannot be talked out of its rules by a document.
"""

from __future__ import annotations

from typing import Any

from .rules import RuleFinding

ACTION_LABELS = {
    "legal_review": "Route the contradicted clause to counsel",
    "request_missing_docs": "Request the missing lease documents",
    "zoning_verification": "Verify the permitted use against municipal zoning records",
    "none": "No action required",
}

CORE_FIELDS = [
    "tenant",
    "landlord",
    "premises_address",
    "lease_start",
    "lease_end",
    "base_rent",
    "permitted_use",
    "assignment_clause",
]


def _claim_stats(grounding: dict[str, Any]) -> dict[str, Any]:
    claims = grounding.get("claims") or []
    contradicted = [c for c in claims if c.get("verdict") == "contradicted"]
    supported = [c for c in claims if c.get("verdict") == "supported"]
    not_stated = [c for c in claims if c.get("verdict") == "not_stated"]
    weight = sum(float(c.get("weight") or 0) for c in contradicted)
    confidence = max((float(c.get("contradicted") or 0) for c in contradicted), default=0.0)
    return {
        "total": len(claims),
        "contradicted": len(contradicted),
        "supported": len(supported),
        "not_stated": len(not_stated),
        "contradicted_weight": round(weight, 3),
        "max_contradiction_confidence": round(confidence, 3),
    }


def assess(
    *,
    grounding: dict[str, Any],
    rule_findings: list[RuleFinding],
    decide: dict[str, Any],
    extracted: dict[str, Any],
) -> dict[str, Any]:
    stats = _claim_stats(grounding)

    model_level = ((decide.get("risk_level") or {}).get("value") or "").upper() or None
    model_probability = (decide.get("compliance_risk_detected") or {}).get("probability")
    model_probability = float(model_probability) if model_probability is not None else None

    fails = [f for f in rule_findings if f.status == "fail"]
    reviews = [f for f in rule_findings if f.status == "review"]
    passes = [f for f in rule_findings if f.status == "pass"]

    missing_fields = [
        name for name in CORE_FIELDS if not ((extracted.get(name) or {}).get("value"))
    ]

    score = 0.0
    rationale: list[str] = []

    if stats["contradicted"]:
        score += min(45.0, 25.0 + stats["contradicted_weight"] * 45.0)
        rationale.append(
            f"{stats['contradicted']} claim(s) contradicted by the regulatory source"
        )
    if fails:
        high = sum(1 for f in fails if f.severity == "high")
        medium = sum(1 for f in fails if f.severity == "medium")
        score += min(40.0, high * 26.0 + medium * 14.0)
        rationale.extend(f"{f.title}: {f.detail}" for f in fails)
    if reviews:
        score += min(14.0, sum(6.0 if f.severity == "medium" else 3.0 for f in reviews))
        rationale.append(f"{len(reviews)} term(s) cannot be verified from the documents supplied")
    if missing_fields:
        score += min(12.0, len(missing_fields) * 2.5)
        rationale.append(f"{len(missing_fields)} core lease field(s) missing")
    if model_probability is not None:
        score += model_probability * 18.0
    score = int(round(max(0.0, min(100.0, score))))

    if fails and any(f.severity == "high" for f in fails):
        level = "HIGH"
    elif stats["max_contradiction_confidence"] >= 0.7:
        level = "HIGH"
    elif model_level == "HIGH":
        level = "HIGH"
    elif score >= 55:
        level = "HIGH"
    elif model_level == "MEDIUM" or reviews or score >= 25 or stats["contradicted"]:
        level = "MEDIUM"
    else:
        level = "LOW"

    escalated = bool(model_level and model_level != level and level == "HIGH")
    if escalated:
        rationale.append(
            f"Escalated from model assessment {model_level} to HIGH by deterministic rules"
        )

    actions: list[str] = list((decide.get("required_actions") or {}).get("value") or [])
    for finding in fails + reviews:
        if finding.action and finding.action not in actions:
            actions.append(finding.action)
    actions = [a for a in actions if a != "none"] or (["none"] if level == "LOW" else [])
    if level == "HIGH" and "legal_review" not in actions:
        actions.insert(0, "legal_review")

    human_review = bool((decide.get("human_review_required") or {}).get("value"))
    if level == "HIGH" or fails:
        human_review = True

    headline = {
        "HIGH": "Do not execute without remediation",
        "MEDIUM": "Execute only after the flagged items are cleared",
        "LOW": "No material compliance conflict detected",
    }[level]

    return {
        "risk_level": level,
        "score": score,
        "headline": headline,
        "model_level": model_level,
        "escalated": escalated,
        "compliance_risk_detected": {
            "value": level in {"HIGH", "MEDIUM"},
            "probability": model_probability,
        },
        "human_review_required": {
            "value": human_review,
            "probability": (decide.get("human_review_required") or {}).get("probability"),
        },
        "required_actions": actions,
        "action_labels": {a: ACTION_LABELS.get(a, a) for a in actions},
        "claim_stats": stats,
        "rule_stats": {
            "fail": len(fails),
            "review": len(reviews),
            "pass": len(passes),
            "total": len(rule_findings),
        },
        "missing_fields": missing_fields,
        "rationale": rationale,
        "model_probabilities": (decide.get("risk_level") or {}).get("probabilities", {}),
    }
