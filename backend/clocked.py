"""Typed wrappers around the Clocked API.

Every step the product performs is a real Clocked call; nothing here is mocked.
The wrappers normalise Clocked's response shapes so the rest of the application
never depends on wire format details, and they translate failures into a single
sanitised `PipelineError` (no keys, prompts, or provider internals leak).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from clocked_sdk import Clocked
from clocked_sdk.errors import ClockedError

from .config import get_settings

logger = logging.getLogger("audittrail.clocked")

PII_ENTITY_KINDS = [
    "person",
    "email",
    "phone",
    "address",
    "ssn",
    "credit_card",
    "bank_account",
    "ip_address",
    "date_of_birth",
    "organization",
]

PII_INSTRUCTIONS = (
    "Mask real party names, contact details, and identifiers. Do not treat "
    "defined role terms (Tenant, Landlord, Lessee, Lessor, Guarantor, Premises) "
    "as personal data. Keep every mention of the same real entity identical."
)

LEASE_FIELDS: dict[str, str] = {
    "tenant": "Full legal name of the tenant exactly as written",
    "landlord": "Full legal name of the landlord exactly as written",
    "premises_address": "Street address of the leased premises",
    "floor_area_sqm": "Approximate floor area of the premises in square metres",
    "lease_start": "Commencement date of the lease term",
    "lease_end": "Expiration date of the lease term",
    "base_rent": "Base rent amount including currency, as written",
    "escalation": "Annual rent escalation or review mechanism, as written",
    "permitted_use": "The permitted use clause of the premises",
    "parking_bays": "Number of parking bays allocated to the tenant",
    "signage": "Signage rights granted to the tenant",
    "assignment_clause": "Assignment or subletting clause text",
}

EXTRACT_INSTRUCTIONS = (
    "Read the lease agreement. Copy values verbatim from the text: do not "
    "summarise, normalise, or invent values. If the document does not state a "
    "field, leave it empty. Numbers must be copied exactly as written."
)


@dataclass
class StepResult:
    """One Clocked call plus the timing the UI shows to the user."""

    name: str
    data: dict[str, Any]
    ms: int
    meta: dict[str, Any] = field(default_factory=dict)
    model_ms: float | None = None


class PipelineError(RuntimeError):
    """Sanitised pipeline failure that is safe to return over HTTP."""

    def __init__(self, step: str, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.step = step
        self.retryable = retryable


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        return dict(value)  # clocked_sdk.Result is mapping-like
    except Exception:  # pragma: no cover - defensive
        return {}


def _norm_noul(answer: Any) -> dict[str, Any]:
    """Normalise a yes/no-with-probability answer."""
    if isinstance(answer, bool):
        return {"value": answer, "probability": 1.0 if answer else 0.0}
    if not isinstance(answer, dict):
        return {"value": None, "probability": None}
    probability = answer.get("noul", answer.get("probability"))
    decision = answer.get("decision", answer.get("value"))
    if decision is None and probability is not None:
        decision = bool(probability >= float(answer.get("threshold", 0.5)))
    return {"value": decision, "probability": probability, "threshold": answer.get("threshold")}


def _norm_choice(answer: Any) -> dict[str, Any]:
    if isinstance(answer, str):
        return {"value": answer, "probabilities": {}, "confidence": None}
    if not isinstance(answer, dict):
        return {"value": None, "probabilities": {}, "confidence": None}
    return {
        "value": answer.get("choice", answer.get("value")),
        "probabilities": answer.get("probabilities", answer.get("scores", {})) or {},
        "confidence": answer.get("confidence"),
    }


def _norm_multi(answer: Any) -> dict[str, Any]:
    if isinstance(answer, list):
        return {"value": answer, "probabilities": {}}
    if not isinstance(answer, dict):
        return {"value": [], "probabilities": {}}
    selected = answer.get("selected", answer.get("value", []))
    return {"value": list(selected or []), "probabilities": answer.get("probabilities", {}) or {}}


def normalise_decide(answers: dict[str, Any]) -> dict[str, Any]:
    """Turn Clocked's typed answers into a flat, UI-friendly structure."""
    out: dict[str, Any] = {}
    for name, answer in (answers or {}).items():
        kind = answer.get("type") if isinstance(answer, dict) else None
        if kind == "noul":
            out[name] = _norm_noul(answer)
        elif kind == "choice":
            out[name] = _norm_choice(answer)
        elif kind == "multiselect":
            out[name] = _norm_multi(answer)
        elif isinstance(answer, dict):
            out[name] = {"value": answer.get("value"), **answer}
        else:
            out[name] = {"value": answer}
    return out


class ClockedGateway:
    """Thin, testable seam over the official Clocked SDK."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        settings = get_settings()
        self._settings = settings
        self._api_key = api_key if api_key is not None else settings.clocked_api_key
        self._base_url = base_url or settings.clocked_api_url
        self._client: Clocked | None = None

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self) -> Clocked:
        if self._client is None:
            if not self._api_key:
                raise PipelineError(
                    "config",
                    "CLOCKED_API_KEY is not configured on the server.",
                    retryable=False,
                )
            self._client = Clocked(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._settings.clocked_timeout,
            )
        return self._client

    def _call(self, step: str, fn, **kwargs) -> StepResult:
        started = time.perf_counter()
        try:
            result = _as_dict(fn(**kwargs))
        except ClockedError as exc:  # SDK error hierarchy
            logger.warning("Clocked step %s failed: %s", step, exc.__class__.__name__)
            raise PipelineError(step, f"Clocked {step} call failed: {exc}") from exc
        except Exception as exc:  # pragma: no cover - network/transport
            logger.exception("Unexpected failure in Clocked step %s", step)
            raise PipelineError(step, f"Clocked {step} call failed unexpectedly.") from exc
        timing = result.get("timing") or {}
        model_ms = timing.get("total_ms") if isinstance(timing, dict) else None
        return StepResult(step, result, int((time.perf_counter() - started) * 1000), model_ms=model_ms)

    # ------------------------------------------------------------------ steps

    def protect(self, text: str) -> StepResult:
        return self._call(
            "protect",
            self._get_client().pii,
            text=text,
            entities=PII_ENTITY_KINDS,
            anonymize="replace",
            threshold=0.45,
            instructions=PII_INSTRUCTIONS,
        )

    def guard(self, text: str) -> StepResult:
        return self._call(
            "guard",
            self._get_client().injection,
            text=text,
            source="content",
            evidence=True,
        )

    def extract(self, text: str) -> StepResult:
        result = self._call(
            "extract",
            self._get_client().extract,
            text=text,
            fields=LEASE_FIELDS,
            instructions=EXTRACT_INSTRUCTIONS,
        )
        fields = {}
        for name, field_value in (result.data.get("fields") or {}).items():
            if isinstance(field_value, dict):
                fields[name] = {
                    "value": field_value.get("value"),
                    "start": field_value.get("start"),
                    "end": field_value.get("end"),
                    "confidence": field_value.get("confidence"),
                }
        result.data["fields"] = fields
        return result

    def ground(
        self,
        *,
        claims: Iterable[str],
        answer: str,
        source_text: str,
        source_id: str = "regulatory-source",
    ) -> StepResult:
        result = self._call(
            "verify",
            self._get_client().grounding,
            documents=[{"id": source_id, "text": source_text}],
            answer=answer,
            claims=list(claims),
            evidence="all",
            threshold=0.55,
            instructions=(
                "Judge every claim only against the supplied regulatory source. "
                "Distinguish 'not stated in the source' from 'contradicted by the "
                "source'. Missing evidence is not proof of non-compliance. Do not "
                "perform arithmetic; report only what the source states."
            ),
        )
        result.data["claims"] = [
            {
                "claim": c.get("claim"),
                "verdict": c.get("verdict"),
                "supported": c.get("supported"),
                "contradicted": c.get("contradicted"),
                "not_stated": c.get("not_stated"),
                "weight": c.get("weight"),
                "source": c.get("source"),
                "evidence_quote": (c.get("evidence") or {}).get("quote"),
                "evidence_document": (c.get("evidence") or {}).get("document"),
                "evidence_start": (c.get("evidence") or {}).get("start"),
                "evidence_end": (c.get("evidence") or {}).get("end"),
            }
            for c in result.data.get("claims", [])
        ]
        return result

    def decide(self, *, state: str) -> StepResult:
        result = self._call(
            "decide",
            self._get_client().decide,
            state=state,
            instructions=(
                "Assess this commercial lease audit for zoning and regulatory "
                "compliance risk. Judge only from the supplied evidence. A "
                "contradicted claim is high risk; a core term absent from the "
                "regulatory source is medium risk. Missing lease fields are a "
                "documentation risk."
            ),
            questions={
                "compliance_risk_detected": {
                    "type": "noul",
                    "instructions": (
                        "Does the lease contain a zoning or regulatory compliance "
                        "problem evidenced by a contradicted claim or an "
                        "unsupported core term?"
                    ),
                    "threshold": 0.7,
                },
                "risk_level": {
                    "type": "choice",
                    "instructions": "Overall compliance risk level of this lease.",
                    "criteria": {
                        "LOW": "No contradicted claims; only minor or no gaps.",
                        "MEDIUM": "Core terms missing from the regulatory source, or documentation gaps.",
                        "HIGH": "A claim contradicted by the regulatory source, or a prohibited use.",
                    },
                },
                "required_actions": {
                    "type": "multiselect",
                    "instructions": "Which remediation actions does the evidence warrant?",
                    "criteria": {
                        "legal_review": "Route to counsel because a claim is contradicted.",
                        "request_missing_docs": "Ask the counterparty for absent lease fields.",
                        "zoning_verification": "Verify permitted use against municipal zoning records.",
                        "none": "No action required by the evidence supplied.",
                    },
                    "threshold": 0.6,
                },
                "human_review_required": {
                    "type": "noul",
                    "instructions": "Should a compliance officer review this audit before the report is finalised?",
                    "threshold": 0.5,
                },
            },
        )
        result.data["answers"] = normalise_decide(result.data.get("answers") or {})
        return result
