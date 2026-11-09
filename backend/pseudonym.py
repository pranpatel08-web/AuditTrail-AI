"""Consistent pseudonymisation with a re-identification key held by the customer.

Clocked's Protect step finds the sensitive spans. This module turns those spans
into stable tokens such as `[ORG_1]` and `[PERSON_2]` so that:

* the same real entity always maps to the same token (referential integrity:
  the tenant stays distinguishable from the landlord downstream);
* the masked text is still readable by an auditor;
* the mapping back to real values lives only in memory for the duration of the
  request and is offered to the signed-in user as a one-time download. It is
  never written to the database or to logs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# Defined role words are not personal data. Masking them destroys the meaning of
# a lease ("Tenant" and "Landlord" become indistinguishable tokens), so they are
# excluded even if the detector proposes them.
ROLE_TERMS = {
    "tenant",
    "tenants",
    "landlord",
    "landlords",
    "lessee",
    "lessor",
    "subtenant",
    "guarantor",
    "premises",
    "borrower",
    "lender",
    "buyer",
    "seller",
    "assignee",
    "assignor",
    "party",
    "parties",
    "company",
    "counterparty",
}

TOKEN_PREFIX = {
    "person": "PERSON",
    "email": "EMAIL",
    "phone": "PHONE",
    "address": "ADDRESS",
    "ssn": "SSN",
    "credit_card": "CARD",
    "bank_account": "ACCOUNT",
    "ip_address": "IP",
    "date_of_birth": "DOB",
    "organization": "ORG",
}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}(?!\w)")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9.'-]*(?:\s+[A-Z][A-Za-z0-9.'-]*){0,3}\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|"
    r"Place|Pl|Court|Ct|Highway|Hwy|Square|Terrace|Close)\b"
    r"(?:[,\s]+(?:Suite|Unit|Floor|Building|Bldg)\.?\s*[A-Za-z0-9-]+)?"
)


@dataclass
class Finding:
    type: str
    token: str
    start: int
    end: int
    confidence: float | None = None
    value: str | None = None


@dataclass
class MaskResult:
    text: str
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    vault: dict[str, str] = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.vault)

    @property
    def mentions(self) -> int:
        return len(self.findings)


def _luhn(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if len(digits) < 13:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _regex_backstops(text: str) -> list[dict[str, Any]]:
    """Deterministic detectors that run alongside the model.

    Defence in depth: if the model misses a routine identifier, the regex layer
    still removes it. Only high-precision patterns are used.
    """
    found: list[dict[str, Any]] = []

    def add(kind: str, match: re.Match[str], confidence: float = 0.9) -> None:
        value = match.group(0).strip()
        if not value:
            return
        start = match.start() + (len(match.group(0)) - len(match.group(0).lstrip()))
        found.append(
            {
                "type": kind,
                "value": value,
                "start": start,
                "end": start + len(value),
                "confidence": confidence,
            }
        )

    for match in EMAIL_RE.finditer(text):
        add("email", match, 0.99)
    for match in SSN_RE.finditer(text):
        add("ssn", match, 0.99)
    for match in CARD_RE.finditer(text):
        if _luhn(match.group(0)):
            add("credit_card", match, 0.95)
    for match in IP_RE.finditer(text):
        add("ip_address", match, 0.9)
    for match in ADDRESS_RE.finditer(text):
        add("address", match, 0.75)
    for match in PHONE_RE.finditer(text):
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        # Avoid dates, money and short numeric strings.
        if 9 <= len(digits) <= 15 and not re.fullmatch(r"(?:19|20)\d{2}", digits):
            add("phone", match, 0.7)
    return found


def _clean_value(value: str) -> str:
    return value.strip().strip(" .,;:")


def _is_role_term(value: str) -> bool:
    normalised = re.sub(r"[^a-z ]", "", value.lower()).strip()
    if normalised in ROLE_TERMS:
        return True
    # "the Tenant", "Landlord's" etc.
    words = [w for w in normalised.split() if w not in {"the", "a", "an"}]
    return len(words) == 1 and words[0] in ROLE_TERMS


def _merge_adjacent(entities: list[dict[str, Any]], text: str, max_gap: int = 3) -> list[dict[str, Any]]:
    """Join fragments the detector split, e.g. "Verde Coffee" + "Roasters Inc"."""
    ordered = sorted(entities, key=lambda e: (e["start"], -(e["end"] - e["start"])))
    merged: list[dict[str, Any]] = []
    for entity in ordered:
        if merged:
            previous = merged[-1]
            gap = text[previous["end"] : entity["start"]]
            if (
                previous["type"] == entity["type"]
                and 0 <= entity["start"] - previous["end"] <= max_gap
                and not gap.strip(" ,.\t\n")
            ):
                previous["end"] = max(previous["end"], entity["end"])
                previous["value"] = text[previous["start"] : previous["end"]]
                continue
        merged.append(dict(entity))
    return merged


def _dedupe(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the highest-confidence, widest span when candidates overlap."""
    priority = {"ssn": 6, "credit_card": 6, "email": 5, "phone": 4, "address": 3, "ip_address": 3}
    ordered = sorted(
        entities,
        key=lambda e: (-priority.get(e["type"], 1), -(e.get("confidence") or 0), -(e["end"] - e["start"])),
    )
    kept: list[dict[str, Any]] = []
    for entity in ordered:
        if any(not (entity["end"] <= k["start"] or entity["start"] >= k["end"]) for k in kept):
            continue
        kept.append(entity)
    return sorted(kept, key=lambda e: e["start"])


def pseudonymise(text: str, entities: Iterable[dict[str, Any]]) -> MaskResult:
    """Replace every sensitive span with a stable, human-readable token."""
    candidates: list[dict[str, Any]] = []
    for entity in entities or []:
        try:
            start, end = int(entity["start"]), int(entity["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= start < end <= len(text):
            continue
        value = _clean_value(entity.get("value") or text[start:end])
        if not value or _is_role_term(value):
            continue
        candidates.append(
            {
                "type": entity.get("type") or "entity",
                "value": value,
                "start": start,
                "end": end,
                "confidence": entity.get("confidence"),
            }
        )

    candidates.extend(_regex_backstops(text))
    candidates = _dedupe(_merge_adjacent(candidates, text))

    tokens: dict[tuple[str, str], str] = {}
    counters: dict[str, int] = {}
    findings: list[Finding] = []
    vault: dict[str, str] = {}

    # Assign tokens left-to-right so numbering follows the document.
    for entity in sorted(candidates, key=lambda e: e["start"]):
        key = (entity["type"], " ".join(entity["value"].split()).lower())
        if key not in tokens:
            prefix = TOKEN_PREFIX.get(entity["type"], "ENTITY")
            counters[prefix] = counters.get(prefix, 0) + 1
            token = f"{prefix}_{counters[prefix]}"
            tokens[key] = token
            vault[token] = entity["value"]

    masked = text
    for entity in sorted(candidates, key=lambda e: e["start"], reverse=True):
        key = (entity["type"], " ".join(entity["value"].split()).lower())
        token = tokens[key]
        masked = masked[: entity["start"]] + f"[{token}]" + masked[entity["end"] :]

    # Recompute positions against the masked text for UI highlighting.
    cursor = 0
    for entity in sorted(candidates, key=lambda e: e["start"]):
        key = (entity["type"], " ".join(entity["value"].split()).lower())
        token = tokens[key]
        needle = f"[{token}]"
        position = masked.find(needle, cursor)
        if position == -1:
            continue
        findings.append(
            Finding(
                type=entity["type"],
                token=token,
                start=position,
                end=position + len(needle),
                confidence=entity.get("confidence"),
                value=entity["value"],
            )
        )
        cursor = position + len(needle)

    counts: dict[str, int] = {}
    for entity in candidates:
        counts[entity["type"]] = counts.get(entity["type"], 0) + 1

    return MaskResult(text=masked, findings=findings, counts=counts, vault=vault)
