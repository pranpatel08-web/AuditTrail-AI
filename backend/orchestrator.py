"""Five-step audit orchestration.

protect -> guard -> extract -> verify -> decide, with each step's output
actually changing what the next step does. The orchestrator is the only place
that knows the order, and it records timings so the UI can show the live
pipeline rather than a fake progress bar.
"""

from __future__ import annotations

import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from . import claims as claim_builder
from . import policy, rules
from .clocked import ClockedGateway, PipelineError
from .config import Settings, get_settings
from .pseudonym import pseudonymise

DANGEROUS_VERDICTS = {"dangerous", "dangerous_injection", "injection", "malicious"}


@dataclass
class AuditRun:
    record: dict[str, Any]
    vault: dict[str, str] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.record.get("status") == "blocked"


def _entity_summary(mask) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for finding in mask.findings:
        entry = grouped.setdefault(
            finding.token,
            {"token": finding.token, "type": finding.type, "mentions": 0, "confidence": finding.confidence},
        )
        entry["mentions"] += 1
    return sorted(grouped.values(), key=lambda e: (e["type"], e["token"]))


def run_audit(
    *,
    lease_text: str,
    rules_text: str,
    title: str,
    user_id: str,
    gateway: ClockedGateway | None = None,
    settings: Settings | None = None,
) -> AuditRun:
    settings = settings or get_settings()
    gateway = gateway or ClockedGateway()

    if not gateway.available and settings.fail_closed:
        raise PipelineError("config", "Clocked is not configured; the pipeline fails closed.", retryable=False)

    lease_text = lease_text.strip()
    rules_text = rules_text.strip()
    if not lease_text or not rules_text:
        raise ValueError("Both the lease text and the regulatory source are required.")

    truncated = False
    if len(lease_text) > settings.max_lease_chars:
        lease_text = lease_text[: settings.max_lease_chars]
        truncated = True
    if len(rules_text) > settings.max_rules_chars:
        rules_text = rules_text[: settings.max_rules_chars]
        truncated = True

    started = time.perf_counter()
    steps: list[dict[str, Any]] = []
    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    def record_step(name: str, ms: int, summary: str, **extra: Any) -> None:
        steps.append({"name": name, "ms": ms, "status": "ok", "summary": summary, **extra})

    # ------------------------------------------------------------- 1. protect
    protect = gateway.protect(lease_text)
    entities = protect.data.get("entities") or []
    mask = pseudonymise(lease_text, entities)
    record_step(
        "protect",
        protect.ms,
        f"{mask.entity_count} entities masked across {mask.mentions} mentions",
        entities=mask.entity_count,
        mentions=mask.mentions,
    )

    # --------------------------------------------------------------- 2. guard
    guard = gateway.guard(mask.text)
    verdict = (guard.data.get("verdict") or "").lower()
    guard_meta = {
        "verdict": guard.data.get("verdict"),
        "probability": guard.data.get("injection"),
        "category": guard.data.get("category"),
        "severity": guard.data.get("severity"),
    }
    record_step(
        "guard",
        guard.ms,
        f"{guard_meta['verdict'] or 'unknown'} (p={float(guard_meta['probability'] or 0):.3f})",
    )

    base_record: dict[str, Any] = {
        "id": run_id,
        "created_at": created_at,
        "title": title.strip() or "Untitled lease audit",
        "user_id": user_id,
        "status": "success",
        "engine": "clocked-1.0",
        "document": {
            "lease_chars": len(lease_text),
            "rules_chars": len(rules_text),
            "truncated": truncated,
            "masked_document": mask.text,
        },
        "pii": {
            "counts": mask.counts,
            "entity_count": mask.entity_count,
            "mentions": mask.mentions,
            "entities": _entity_summary(mask),
        },
        "guard": guard_meta,
        "steps": steps,
    }

    if verdict in DANGEROUS_VERDICTS:
        base_record.update(
            {
                "status": "blocked",
                "message": (
                    "Prompt injection was detected in the submitted document. The audit "
                    "stopped before any further model call and was routed to human review."
                ),
            }
        )
        base_record["timings"] = {"total_ms": int((time.perf_counter() - started) * 1000)}
        blocked_ms = sum(r.model_ms or 0 for r in (protect, guard))
        base_record["usage"] = {
            "model_ms": round(blocked_ms),
            "credits": math.ceil(blocked_ms / 25) if blocked_ms else None,
            "cost_usd": round(math.ceil(blocked_ms / 25) * 0.30 / 1000, 4) if blocked_ms else None,
            "rate": "Clocked Build plan · $0.30 per 1,000 credits",
        }
        return AuditRun(record=base_record, vault=mask.vault)

    # ------------------------------------------------------------- 3. extract
    extract = gateway.extract(mask.text)
    extracted = extract.data.get("fields") or {}
    filled = sum(1 for f in extracted.values() if f.get("value"))
    record_step("extract", extract.ms, f"{filled}/{len(extracted)} lease fields read verbatim")

    # -------------------------------------------------------------- 4. verify
    built_claims = claim_builder.build_claims(extracted)
    relevant = [c for c in built_claims if c["probe"] and re.search(c["probe"], rules_text, re.I)]
    skipped = [c["text"] for c in built_claims if c not in relevant]
    claim_list = [c["text"] for c in (relevant or built_claims[:3])]
    answer = claim_builder.build_answer(extracted)
    ground = gateway.ground(claims=claim_list, answer=answer, source_text=rules_text)
    grounding_claims = ground.data.get("claims") or []
    contradicted = sum(1 for c in grounding_claims if c.get("verdict") == "contradicted")
    supported = sum(1 for c in grounding_claims if c.get("verdict") == "supported")
    record_step(
        "verify",
        ground.ms,
        f"{len(grounding_claims)} claims checked: {contradicted} contradicted, {supported} supported",
        contradicted=contradicted,
        supported=supported,
    )

    # ------------------------------------------------------ rules (deterministic)
    rule_findings = rules.evaluate(lease_text, rules_text, extracted)
    failures = [f for f in rule_findings if f.status == "fail"]
    record_step(
        "rules",
        0,
        f"{len(rule_findings)} deterministic checks, {len(failures)} failed",
        fail=len(failures),
    )

    # -------------------------------------------------------------- 5. decide
    state = (
        "Lease document (PII pseudonymised):\n"
        + mask.text[:6000]
        + "\n\nExtracted lease fields: "
        + str({k: (v.get("value") or None) for k, v in extracted.items()})
        + "\n\nGrounding verdict against the regulatory source: "
        + f"{ground.data.get('verdict')} (grounded={ground.data.get('grounded')}). "
        + f"Contradicted claims: {[c.get('claim') for c in grounding_claims if c.get('verdict') == 'contradicted']}. "
        + f"Deterministic rule failures: {[f'{f.title}: {f.detail}' for f in failures] or 'none'}."
    )
    decide = gateway.decide(state=state)
    decision = decide.data.get("answers") or {}
    record_step(
        "decide",
        decide.ms,
        f"{((decision.get('risk_level') or {}).get('value') or 'n/a')} "
        f"(confidence {((decision.get('risk_level') or {}).get('confidence') or 0):.2f})",
    )

    assessment = policy.assess(
        grounding=ground.data,
        rule_findings=rule_findings,
        decide=decision,
        extracted=extracted,
    )

    model_ms = sum(
        result.model_ms or 0 for result in (protect, guard, extract, ground, decide)
    )
    credits = math.ceil(model_ms / 25) if model_ms else None
    base_record["usage"] = {
        "model_ms": round(model_ms),
        "credits": credits,
        "cost_usd": round(credits * 0.30 / 1000, 4) if credits else None,
        "rate": "Clocked Build plan · $0.30 per 1,000 credits · 1 credit = 25 ms model time",
    }

    base_record.update(
        {
            "extracted": extracted,
            "claims": grounding_claims,
            "claims_skipped": skipped,
            "grounding": {
                "verdict": ground.data.get("verdict"),
                "grounded": ground.data.get("grounded"),
                "ungrounded": ground.data.get("ungrounded"),
                "question": "Does this lease comply with the supplied regulatory requirements?",
            },
            "rules": [f.to_dict() for f in rule_findings],
            "decision": decision,
            "risk": assessment,
            "timings": {"total_ms": int((time.perf_counter() - started) * 1000)},
        }
    )
    return AuditRun(record=base_record, vault=mask.vault)
