"""Pre-demo smoke test against the live Clocked API.

    python scripts/smoke.py

Runs the bundled lease through the real pipeline (no HTTP server needed) and
prints the steps, the risk outcome and the measured Clocked usage. Exits
non-zero if the pipeline fails, so it can gate a demo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.clocked import PipelineError  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.orchestrator import run_audit  # noqa: E402


def main() -> int:
    settings = get_settings()
    if not settings.clocked_ready:
        print("FAIL: CLOCKED_API_KEY is not set in .env")
        return 2

    lease = (ROOT / "samples" / "lease_excerpt.txt").read_text(encoding="utf-8")
    zoning = (ROOT / "samples" / "zoning_rules.txt").read_text(encoding="utf-8")

    try:
        run = run_audit(
            lease_text=lease,
            rules_text=zoning,
            title="Smoke test — 412 Harbor Street",
            user_id=settings.demo_user_id,
        )
    except PipelineError as exc:
        print(f"FAIL at step {exc.step}: {exc}")
        return 1

    record = run.record
    risk = record.get("risk") or {}
    print(f"status        {record['status']}")
    for step in record["steps"]:
        print(f"  {step['name']:<10} {step['ms']:>5} ms  {step['summary']}")
    print(f"risk          {risk.get('risk_level')} ({risk.get('score')}/100)")
    print(f"claims        {risk.get('claim_stats')}")
    print(f"rules         {risk.get('rule_stats')}")
    usage = record.get("usage") or {}
    print(f"clocked       {usage.get('credits')} credits · {usage.get('model_ms')} ms · ${usage.get('cost_usd')}")
    print(f"vault         {len(run.vault)} tokens (never persisted)")

    failures = [r for r in record.get("rules", []) if r["status"] == "fail"]
    if not failures:
        print("WARN: expected the sample to trip at least one rule")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
