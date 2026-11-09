"""Deterministic compliance rules.

Models are good at reading contracts and bad at arithmetic. Every numeric or
threshold rule that can be computed is computed here instead of being asked of
the model, and the arithmetic is shown to the user. Clocked Verify handles the
qualitative judgements; this module handles the maths.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from .claims import derive_facts


@dataclass
class RuleFinding:
    id: str
    title: str
    status: str  # pass | fail | review
    severity: str  # high | medium | low | none
    detail: str
    computation: str | None = None
    evidence_quote: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None
    action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
            "computation": self.computation,
            "evidence_quote": self.evidence_quote,
            "evidence_start": self.evidence_start,
            "evidence_end": self.evidence_end,
            "action": self.action,
        }


def _sentence_with(text: str, pattern: str) -> tuple[str | None, int | None, int | None]:
    """Return the sentence containing the first match, with its offsets."""
    match = re.search(pattern, text, re.I | re.S)
    if not match:
        return None, None, None
    start = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start()))
    start = 0 if start == -1 else start + 1
    end_match = re.search(r"[.\n]", text[match.end() :])
    end = match.end() + (end_match.start() if end_match else 0)
    while start < len(text) and text[start].isspace():
        start += 1
    quote = " ".join(text[start:end].split())
    return quote, start, end


def _area_cap(text: str) -> float | None:
    match = re.search(
        r"process area (?:does not exceed|must not exceed|not exceed)\s+(\d+(?:\.\d+)?)\s*(?:percent|%)",
        text,
        re.I,
    )
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s+of (?:the )?total floor area", text, re.I)
    return float(match.group(1)) if match else None


def _signage_cap(text: str) -> float | None:
    match = re.search(r"maximum face area of\s+(\d+(?:\.\d+)?)\s*(?:square meters|sqm|m2)", text, re.I)
    return float(match.group(1)) if match else None


def evaluate(lease_text: str, rules_text: str, extracted: dict[str, Any]) -> list[RuleFinding]:
    facts = derive_facts(extracted)
    findings: list[RuleFinding] = []

    # ---------------------------------------------------------- parking ratio
    parking_rule = re.search(
        r"(?:minimum of\s+)?([a-z0-9]+)\s*\(?(\d+)?\)?\s*parking bays? per\s+(\d+(?:\.\d+)?)\s*"
        r"(?:square meters|sqm|m2)",
        rules_text,
        re.I,
    ) or re.search(
        r"([a-z0-9]+)\s*\(?(\d+)?\)?\s*bays? per\s+(\d+(?:\.\d+)?)\s*(?:square meters|sqm|m2)",
        rules_text,
        re.I,
    )
    if parking_rule and facts["area_sqm"] and facts["parking_bays"] is not None:
        raw_required = parking_rule.group(2) or parking_rule.group(1)
        per_area = float(parking_rule.group(3))
        number_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
        required_per = number_map.get(str(raw_required).lower()) or float(
            re.sub(r"\D", "", str(raw_required)) or 0
        )
        required = math.ceil(facts["area_sqm"] / per_area * required_per)
        allocated = facts["parking_bays"]
        quote, start, end = _sentence_with(rules_text, r"parking bays? per")
        passed = allocated >= required
        findings.append(
            RuleFinding(
                id="parking-ratio",
                title="Minimum parking allocation",
                status="pass" if passed else "fail",
                severity="none" if passed else "high",
                detail=(
                    f"The lease allocates {allocated} bays; the source requires at least "
                    f"{required} for {facts['area_sqm']:.0f} sqm."
                    + ("" if passed else f" Shortfall of {required - allocated} bay(s).")
                ),
                computation=(
                    f"ceil({facts['area_sqm']:.0f} ÷ {per_area:g} × {required_per:g}) "
                    f"= {required} required vs {allocated} allocated"
                ),
                evidence_quote=quote,
                evidence_start=start,
                evidence_end=end,
                action=None if passed else "zoning_verification",
            )
        )

    # --------------------------------------------------- entertainment permit
    permit_rule = re.search(r"(?:supplementary\s+)?entertainment permit", rules_text, re.I)
    if permit_rule and facts["mentions_entertainment"] and facts["mentions_after_22"]:
        quote, start, end = _sentence_with(rules_text, r"entertainment permit")
        findings.append(
            RuleFinding(
                id="entertainment-permit",
                title="Late-night entertainment licensing",
                status="fail",
                severity="high",
                detail=(
                    "The lease allows live entertainment after 22:00 on the landlord's "
                    "consent alone, but the regulatory source requires a separate "
                    "entertainment permit from the licensing board."
                ),
                computation="Landlord consent alone ≠ statutory entertainment permit",
                evidence_quote=quote,
                evidence_start=start,
                evidence_end=end,
                action="legal_review",
            )
        )

    # ------------------------------------------------------ roasting area cap
    cap = _area_cap(rules_text)
    if cap is not None and facts["mentions_roasting"]:
        stated_area = re.search(r"(?:roasting|process)\s+area[^.\d]{0,40}(\d+(?:\.\d+)?)\s*(?:square meters|sqm|m2)", lease_text, re.I)
        if stated_area and facts["area_sqm"]:
            process_area = float(stated_area.group(1))
            share = process_area / facts["area_sqm"] * 100
            passed = share <= cap
            quote, start, end = _sentence_with(rules_text, r"process area")
            findings.append(
                RuleFinding(
                    id="roasting-area",
                    title="Roasting process area cap",
                    status="pass" if passed else "fail",
                    severity="none" if passed else "high",
                    detail=(
                        f"The roasting area is {process_area:.0f} sqm ({share:.1f}% of floor area); "
                        f"the source caps it at {cap:g}%."
                    ),
                    computation=f"{process_area:.0f} ÷ {facts['area_sqm']:.0f} × 100 = {share:.1f}% vs cap {cap:g}%",
                    evidence_quote=quote,
                    evidence_start=start,
                    evidence_end=end,
                    action=None if passed else "zoning_verification",
                )
            )
        else:
            quote, start, end = _sentence_with(rules_text, r"process area")
            findings.append(
                RuleFinding(
                    id="roasting-area",
                    title="Roasting process area cap",
                    status="review",
                    severity="medium",
                    detail=(
                        f"The source caps the roasting process area at {cap:g}% of floor area, "
                        "but the lease does not state the process area. Cannot be verified "
                        "from the document alone."
                    ),
                    computation=f"process area ÷ {facts['area_sqm']:.0f} sqm must be ≤ {cap:g}%",
                    evidence_quote=quote,
                    evidence_start=start,
                    evidence_end=end,
                    action="request_missing_docs",
                )
            )

    # ------------------------------------------------------------- signage
    signage_cap = _signage_cap(rules_text)
    signage_text = (extracted.get("signage") or {}).get("value") or ""
    if signage_cap is not None and signage_text:
        size = re.search(r"(\d+(?:\.\d+)?)\s*(?:square meters|sqm|m2)", signage_text, re.I)
        quote, start, end = _sentence_with(rules_text, r"maximum face area")
        if size:
            face = float(size.group(1))
            passed = face <= signage_cap
            findings.append(
                RuleFinding(
                    id="signage-area",
                    title="Exterior signage face area",
                    status="pass" if passed else "fail",
                    severity="none" if passed else "medium",
                    detail=f"The sign face is {face:g} sqm; the source caps it at {signage_cap:g} sqm.",
                    computation=f"{face:g} sqm vs cap {signage_cap:g} sqm",
                    evidence_quote=quote,
                    evidence_start=start,
                    evidence_end=end,
                    action=None if passed else "zoning_verification",
                )
            )
        else:
            findings.append(
                RuleFinding(
                    id="signage-area",
                    title="Exterior signage face area",
                    status="review",
                    severity="low",
                    detail=(
                        f"The source caps sign face area at {signage_cap:g} sqm, but the lease "
                        "does not state the size of the permitted sign."
                    ),
                    computation=f"sign face must be ≤ {signage_cap:g} sqm",
                    evidence_quote=quote,
                    evidence_start=start,
                    evidence_end=end,
                    action="request_missing_docs",
                )
            )

    # ------------------------------------------------------- delivery window
    delivery_rule = re.search(
        r"service bays? between\s+(\d{1,2}:\d{2})\s*and\s*(\d{1,2}:\d{2})", rules_text, re.I
    )
    delivery_lease = re.search(
        r"service bay between\s+(\d{1,2}:\d{2})\s*and\s*(\d{1,2}:\d{2})", lease_text, re.I
    )
    if delivery_rule and delivery_lease:
        allowed = (delivery_rule.group(1), delivery_rule.group(2))
        used = (delivery_lease.group(1), delivery_lease.group(2))
        quote, start, end = _sentence_with(rules_text, r"service bays? between")
        passed = used == allowed
        findings.append(
            RuleFinding(
                id="delivery-window",
                title="Service bay delivery window",
                status="pass" if passed else "fail",
                severity="none" if passed else "medium",
                detail=f"Lease window {used[0]}–{used[1]}; permitted window {allowed[0]}–{allowed[1]}.",
                computation=f"{used[0]}–{used[1]} {'⊆' if passed else '⊄'} {allowed[0]}–{allowed[1]}",
                evidence_quote=quote,
                evidence_start=start,
                evidence_end=end,
                action=None if passed else "zoning_verification",
            )
        )

    # -------------------------------------------------------- assignment law
    assignment_rule = re.search(r"sole discretion[^.]{0,120}lawful", rules_text, re.I)
    assignment_lease = (extracted.get("assignment_clause") or {}).get("value") or ""
    if assignment_rule and re.search(r"sole discretion", assignment_lease, re.I):
        quote, start, end = _sentence_with(rules_text, r"sole discretion")
        findings.append(
            RuleFinding(
                id="assignment-consent",
                title="Assignment consent standard",
                status="pass",
                severity="none",
                detail=(
                    "The lease allows consent to be withheld at the landlord's sole "
                    "discretion; the regulatory source expressly permits this."
                ),
                computation="Lease clause matches permitted standard",
                evidence_quote=quote,
                evidence_start=start,
                evidence_end=end,
            )
        )

    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    return sorted(findings, key=lambda f: (order.get(f.severity, 9), f.id))
