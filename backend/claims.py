"""Turn extracted lease fields into explicit, checkable claims.

Grounding is only as good as the claims it is given. Feeding a whole document
produces noisy "not_a_claim" fragments, so we build a short list of operative
claims from the fields Clocked Extract returned, plus the numeric facts the
deterministic rule engine needs.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _value(extracted: dict[str, Any], key: str) -> str | None:
    field = extracted.get(key) or {}
    value = field.get("value") if isinstance(field, dict) else field
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_number(text: str | None) -> float | None:
    """Read the first number in a string, including simple word numbers."""
    if not text:
        return None
    cleaned = text.replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if match:
        return float(match.group(0))
    lowered = cleaned.lower()
    for word, number in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            return float(number)
    return None


def parse_money(text: str | None) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    currency_match = re.search(r"\b(USD|EUR|GBP|ZMW|ZAR|KES|NGN|INR|AUD|CAD|CHF|AED)\b", text.upper())
    symbol_map = {"$": "USD", "€": "EUR", "£": "GBP"}
    symbol = next((s for s in symbol_map if s in text), None)
    currency = currency_match.group(1) if currency_match else symbol_map.get(symbol or "")
    return parse_number(text), currency


def parse_date(text: str | None) -> date | None:
    """Best-effort date parsing for the formats leases actually use."""
    if not text:
        return None
    raw = text.strip().replace(",", " ")
    candidates = [
        "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
        "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m-%d",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(" ".join(raw.split()), fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if match:
        month = MONTHS.get(match.group(2).lower())
        if month:
            return date(int(match.group(3)), month, int(match.group(1)))
    match = re.search(r"([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})", raw)
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month:
            return date(int(match.group(3)), month, int(match.group(2)))
    return None


def derive_facts(extracted: dict[str, Any]) -> dict[str, Any]:
    """Numeric facts used by both the claim builder and the rule engine."""
    area = parse_number(_value(extracted, "floor_area_sqm"))
    bays = parse_number(_value(extracted, "parking_bays"))
    rent, currency = parse_money(_value(extracted, "base_rent"))
    escalation_text = _value(extracted, "escalation") or ""
    escalation = parse_number(escalation_text) if "%" in escalation_text or "percent" in escalation_text.lower() else None
    start = parse_date(_value(extracted, "lease_start"))
    end = parse_date(_value(extracted, "lease_end"))
    term_years = None
    if start and end and end > start:
        term_years = round((end - start).days / 365.25, 1)
    permitted_use = _value(extracted, "permitted_use") or ""
    return {
        "area_sqm": area,
        "parking_bays": int(bays) if bays is not None else None,
        "rent": rent,
        "currency": currency,
        "escalation_pct": escalation,
        "start": start,
        "end": end,
        "term_years": term_years,
        "permitted_use": permitted_use,
        "mentions_roasting": bool(re.search(r"roast|baker|heat[- ]treat", permitted_use, re.I)),
        "mentions_entertainment": bool(re.search(r"live entertainment|nightclub|bar\b", permitted_use, re.I)),
        "mentions_after_22": bool(re.search(r"after\s+22[:.]?00|after\s+10\s*p", permitted_use, re.I)),
    }


def _short(text: str | None, limit: int = 240) -> str:
    if not text:
        return ""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _clean_use_clause(text: str) -> str:
    """Reduce a long permitted-use clause to its operative first sentence."""
    flat = " ".join((text or "").split())
    flat = re.sub(
        r"^(?:the premises (?:shall|may) be used (?:solely )?(?:for|as)(?: the)?(?: operation of)?\s*)",
        "",
        flat,
        flags=re.I,
    )
    first = re.split(r"(?<=[.;])\s", flat, maxsplit=1)[0]
    return _short(first.rstrip(".;"), 200)


def build_claims(extracted: dict[str, Any]) -> list[dict[str, str]]:
    """Operative claims, each tagged with the source vocabulary it depends on.

    A regulatory source cannot adjudicate rent or term length. Sending those
    claims produces a wall of meaningless "not stated" verdicts, so each claim
    carries a probe: if the supplied source never mentions the topic, the claim
    is extracted for the report but not put to Verify.
    """
    facts = derive_facts(extracted)
    claims: list[dict[str, str]] = []

    if facts["parking_bays"] is not None:
        text = (
            f"The lease allocates {facts['parking_bays']} parking bays to the tenant"
            + (f" for a premises of approximately {facts['area_sqm']:.0f} square meters."
               if facts["area_sqm"] else ".")
        )
        claims.append({"text": text, "probe": None})

    permitted = _clean_use_clause(facts["permitted_use"])
    if permitted:
        claims.append({"text": f"The lease permits: {permitted}.", "probe": r"permitted use|ground[- ]floor|zoning|retail|food|beverage"})

    if facts["mentions_roasting"] and "roast" not in permitted.lower():
        claims.append(
            {
                "text": "The lease permits on-site roasting for wholesale distribution.",
                "probe": r"roast|baker|heat[- ]treat|ventilation",
            }
        )

    if facts["mentions_entertainment"] and facts["mentions_after_22"]:
        claims.append(
            {
                "text": (
                    "The lease permits live entertainment after 22:00 with the landlord's "
                    "written consent alone, without a separate entertainment permit."
                ),
                "probe": r"entertainment|licen[cs]e|liquor|nightclub|bar\b",
            }
        )

    signage = _short(_value(extracted, "signage"))
    if signage:
        claims.append({"text": f"The lease grants signage rights: {signage}", "probe": r"sign"})

    if facts["term_years"]:
        claims.append(
            {
                "text": f"The lease has an initial term of {facts['term_years']:g} years.",
                "probe": r"term|tenure|duration|leasehold",
            }
        )

    if facts["rent"]:
        rent_claim = f"The base rent is {facts['currency'] or ''} {facts['rent']:,.0f} per month".replace("  ", " ")
        if facts["escalation_pct"]:
            rent_claim += f" with an annual escalation of {facts['escalation_pct']:g} percent"
        claims.append({"text": rent_claim + ".", "probe": r"rent|escalation|review|indexation"})

    assignment = _short(_value(extracted, "assignment_clause"))
    if assignment:
        claims.append(
            {
                "text": (
                    "The lease permits assignment or subletting only with the landlord's prior "
                    "written consent, which may be withheld at the landlord's sole discretion."
                    if re.search(r"sole discretion", assignment, re.I)
                    else f"The lease's assignment provision is: {assignment}"
                ),
                "probe": r"assign|sublet|sublease|transfer",
            }
        )

    # Keep the grounding request focused; more than eight claims dilutes weights.
    return claims[:8]


def build_answer(extracted: dict[str, Any]) -> str:
    """Non-empty factual summary required by the grounding endpoint."""
    facts = derive_facts(extracted)
    parts: list[str] = []
    if facts["area_sqm"]:
        parts.append(f"a {facts['area_sqm']:.0f} sqm premises")
    if facts["parking_bays"] is not None:
        parts.append(f"{facts['parking_bays']} allocated parking bays")
    if facts["term_years"]:
        parts.append(f"a {facts['term_years']:g}-year initial term")
    if facts["rent"]:
        parts.append(f"base rent of {facts['currency'] or ''} {facts['rent']:,.0f} per month".replace("  ", " "))
    use = _short(facts["permitted_use"], 180)
    if use:
        parts.append(f"permitted use: {use}")
    if not parts:
        return "Operative lease terms extracted from the submitted document."
    return "The submitted lease provides for " + ", ".join(parts) + "."
