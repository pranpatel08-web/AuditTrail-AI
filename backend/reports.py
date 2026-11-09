"""Audit report rendering: Markdown for tooling, HTML for print-to-PDF.

The report is the billable artifact, so it is written to be handed to a client:
evidence quotes with offsets, the arithmetic behind every deterministic check,
and a clear statement of what the audit did not cover.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any

VERDICT_LABEL = {
    "supported": "Supported",
    "contradicted": "Contradicted",
    "not_stated": "Not stated in source",
    "not_a_claim": "Not a claim",
}

STATUS_LABEL = {"pass": "Pass", "fail": "Fail", "review": "Needs review"}


def _fmt_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return value


def _risk(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("risk") or {}


def _claims(record: dict[str, Any]) -> list[dict[str, Any]]:
    return record.get("claims") or []


def render_markdown(record: dict[str, Any], *, org_name: str | None = None) -> str:
    risk = _risk(record)
    lines: list[str] = []
    brand = org_name or "AuditTrail AI"
    lines.append(f"# Compliance Audit Report — {record.get('title', 'Untitled')}")
    lines.append("")
    lines.append(f"**Prepared by:** {brand}  ")
    lines.append(f"**Audit ID:** `{record.get('id')}`  ")
    lines.append(f"**Date:** {_fmt_date(record.get('created_at'))}  ")
    lines.append(f"**Engine:** Clocked 5-step pipeline (protect → guard → extract → verify → decide)")
    lines.append("")

    lines.append("## 1. Outcome")
    lines.append("")
    lines.append(f"**Risk level: {risk.get('risk_level', '-')}** — score {risk.get('score', 0)}/100")
    lines.append("")
    lines.append(f"{risk.get('headline', '')}")
    lines.append("")
    if risk.get("rationale"):
        lines.append("Why:")
        for reason in risk["rationale"]:
            lines.append(f"- {reason}")
        lines.append("")

    lines.append("### Required actions")
    lines.append("")
    labels = risk.get("action_labels") or {}
    actions = risk.get("required_actions") or []
    if actions:
        for action in actions:
            lines.append(f"- [ ] {labels.get(action, action)}")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("## 2. Claim-by-claim verification")
    lines.append("")
    lines.append("| # | Claim | Verdict | Evidence from the regulatory source |")
    lines.append("|---|-------|---------|-------------------------------------|")
    for index, claim in enumerate(_claims(record), 1):
        verdict = VERDICT_LABEL.get(claim.get("verdict"), claim.get("verdict") or "-")
        evidence = (claim.get("evidence_quote") or "—").replace("|", "\\|")
        text = (claim.get("claim") or "").replace("|", "\\|")
        lines.append(f"| {index} | {text} | {verdict} | {evidence} |")
    lines.append("")

    lines.append("## 3. Deterministic checks (arithmetic, not model judgement)")
    lines.append("")
    rules = record.get("rules") or []
    if rules:
        lines.append("| Check | Result | Computation | Evidence |")
        lines.append("|-------|--------|-------------|----------|")
        for rule in rules:
            lines.append(
                f"| {rule.get('title')} | {STATUS_LABEL.get(rule.get('status'), rule.get('status'))} "
                f"| {rule.get('computation') or '—'} | {(rule.get('evidence_quote') or '—').replace('|', '/')} |"
            )
    else:
        lines.append("_No deterministic rule matched the documents supplied._")
    lines.append("")

    lines.append("## 4. Extracted lease terms")
    lines.append("")
    lines.append("| Field | Value (pseudonymised) |")
    lines.append("|-------|-----------------------|")
    for name, field in (record.get("extracted") or {}).items():
        value = field.get("value") if isinstance(field, dict) else field
        lines.append(f"| {name.replace('_', ' ').title()} | {(value or '—')} |")
    lines.append("")

    lines.append("## 5. Privacy handling")
    lines.append("")
    pii = record.get("pii") or {}
    lines.append(
        f"- {pii.get('entity_count', 0)} entities pseudonymised across {pii.get('mentions', 0)} mentions."
    )
    for kind, count in sorted((pii.get("counts") or {}).items()):
        lines.append(f"- {kind}: {count}")
    lines.append(
        "- Raw identifiers were replaced before extraction, verification and decision. "
        "The re-identification key is held by the report owner and is not stored with this audit."
    )
    lines.append("")

    lines.append("## 6. Method and limitations")
    lines.append("")
    usage = record.get("usage") or {}
    if usage.get("credits") is not None:
        lines.append(
            f"**Clocked usage:** {usage['credits']} credits across five calls "
            f"({usage.get('model_ms', 0)} ms of model time, about ${usage.get('cost_usd') or 0:.3f} at Build rates)."
        )
        lines.append("")
    lines.append(
        "The regulatory source supplied with the audit is the only authority used for "
        "verification. A term is marked *not stated* when the source is silent; absence "
        "of a rule is not evidence of compliance. This report is a decision-support "
        "artifact and is not legal advice."
    )
    lines.append("")
    lines.append("---")
    lines.append(f"Generated by {brand} · AuditTrail AI v2.0")
    return "\n".join(lines)


def _risk_class(level: str | None) -> str:
    return {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(level or "", "low")


def render_html(record: dict[str, Any], *, org_name: str | None = None) -> str:
    risk = _risk(record)
    brand = html.escape(org_name or "AuditTrail AI")
    level = risk.get("risk_level") or "-"
    esc = html.escape

    claim_rows = []
    for index, claim in enumerate(_claims(record), 1):
        verdict = (claim.get("verdict") or "").replace("_", " ")
        claim_rows.append(
            f"""<tr>
  <td class="num">{index}</td>
  <td>{esc(claim.get('claim') or '')}</td>
  <td><span class="pill {esc(claim.get('verdict') or '')}">{esc(VERDICT_LABEL.get(claim.get('verdict'), verdict))}</span></td>
  <td class="quote">{esc(claim.get('evidence_quote') or '—')}</td>
</tr>"""
        )

    rule_rows = []
    for rule in record.get("rules") or []:
        rule_rows.append(
            f"""<tr>
  <td>{esc(rule.get('title') or '')}</td>
  <td><span class="pill {esc(rule.get('status') or '')}">{esc(STATUS_LABEL.get(rule.get('status'), rule.get('status') or ''))}</span></td>
  <td class="mono">{esc(rule.get('computation') or '—')}</td>
  <td class="quote">{esc(rule.get('evidence_quote') or '—')}</td>
</tr>"""
        )

    field_rows = []
    for name, field in (record.get("extracted") or {}).items():
        value = field.get("value") if isinstance(field, dict) else field
        field_rows.append(
            f"<tr><th>{esc(name.replace('_', ' ').title())}</th><td>{esc(str(value) if value else '—')}</td></tr>"
        )

    pii = record.get("pii") or {}
    pii_rows = "".join(
        f"<li><span>{esc(kind)}</span><strong>{count}</strong></li>"
        for kind, count in sorted((pii.get("counts") or {}).items())
    )

    labels = risk.get("action_labels") or {}
    actions = "".join(
        f"<li>{esc(labels.get(a, a))}</li>" for a in (risk.get("required_actions") or [])
    ) or "<li>None.</li>"

    reasons = "".join(f"<li>{esc(r)}</li>" for r in (risk.get("rationale") or []))
    stats = risk.get("claim_stats") or {}

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(record.get('title', 'Compliance audit'))} — {brand}</title>
<style>
  :root {{ --ink:#111827; --muted:#6b7280; --line:#e5e7eb; --paper:#ffffff; --accent:#0f766e; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#f4f4f2; color:var(--ink); font:15px/1.55 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .page {{ max-width:900px; margin:32px auto; background:var(--paper); padding:56px 60px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  header {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid var(--ink); padding-bottom:20px; }}
  .brand {{ font-weight:700; letter-spacing:.14em; text-transform:uppercase; font-size:12px; }}
  h1 {{ font-size:26px; line-height:1.2; margin:6px 0 0; letter-spacing:-.02em; }}
  h2 {{ font-size:13px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin:40px 0 12px; }}
  .meta {{ font-size:12px; color:var(--muted); text-align:right; }}
  .banner {{ display:flex; align-items:center; gap:24px; margin-top:28px; padding:22px 24px; border-left:6px solid var(--accent); background:#f8faf9; }}
  .banner.high {{ border-color:#b91c1c; background:#fdf3f3; }}
  .banner.medium {{ border-color:#b45309; background:#fdf8f0; }}
  .banner.low {{ border-color:#0f766e; background:#f2f8f7; }}
  .level {{ font-size:38px; font-weight:800; letter-spacing:-.03em; }}
  .score {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }}
  .headline {{ font-weight:600; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); font-weight:600; }}
  td.num {{ width:28px; color:var(--muted); }}
  .quote {{ color:#374151; font-size:12.5px; }}
  .mono {{ font-family:"JetBrains Mono",ui-monospace,monospace; font-size:11.5px; }}
  .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; white-space:nowrap; border:1px solid; }}
  .pill.supported, .pill.pass {{ color:#065f46; background:#ecfdf5; border-color:#a7f3d0; }}
  .pill.contradicted, .pill.fail {{ color:#991b1b; background:#fef2f2; border-color:#fecaca; }}
  .pill.not_stated, .pill.review {{ color:#92400e; background:#fffbeb; border-color:#fde68a; }}
  ul {{ margin:8px 0; padding-left:20px; }}
  .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:32px; }}
  .pii li {{ display:flex; justify-content:space-between; border-bottom:1px dotted var(--line); padding:4px 0; font-size:13px; }}
  pre {{ white-space:pre-wrap; font:11.5px/1.5 ui-monospace,monospace; background:#f9fafb; border:1px solid var(--line); padding:14px; max-height:320px; overflow:auto; }}
  footer {{ margin-top:44px; padding-top:14px; border-top:1px solid var(--line); font-size:11px; color:var(--muted); display:flex; justify-content:space-between; }}
  @media print {{ body {{ background:#fff; }} .page {{ box-shadow:none; margin:0; padding:24mm 18mm; max-width:none; }} }}
</style></head>
<body><div class="page">
<header>
  <div><div class="brand">{brand}</div><h1>{esc(record.get('title', 'Compliance audit'))}</h1></div>
  <div class="meta">Audit ID {esc(record.get('id', ''))}<br>{_fmt_date(record.get('created_at'))}<br>Clocked 5-step pipeline</div>
</header>

<div class="banner {_risk_class(level)}">
  <div><div class="level">{esc(level)}</div><div class="score">Risk score {risk.get('score', 0)}/100</div></div>
  <div><div class="headline">{esc(risk.get('headline', ''))}</div>
  <div class="score">{stats.get('contradicted', 0)} contradicted · {stats.get('supported', 0)} supported · {(risk.get('rule_stats') or {}).get('fail', 0)} rule failures</div></div>
</div>

<h2>Why this outcome</h2><ul>{reasons or '<li>No material findings.</li>'}</ul>
<h2>Required actions</h2><ul>{actions}</ul>

<h2>Claim-by-claim verification</h2>
<table><thead><tr><th>#</th><th>Claim</th><th>Verdict</th><th>Evidence from the regulatory source</th></tr></thead>
<tbody>{''.join(claim_rows) or '<tr><td colspan="4">No claims were checked.</td></tr>'}</tbody></table>

<h2>Deterministic checks</h2>
<table><thead><tr><th>Check</th><th>Result</th><th>Computation</th><th>Evidence</th></tr></thead>
<tbody>{''.join(rule_rows) or '<tr><td colspan="4">No deterministic rule matched the documents supplied.</td></tr>'}</tbody></table>

<div class="cols">
  <div><h2>Extracted lease terms</h2><table><tbody>{''.join(field_rows)}</tbody></table></div>
  <div><h2>Privacy handling</h2>
    <p class="quote">{pii.get('entity_count', 0)} entities pseudonymised across {pii.get('mentions', 0)} mentions.</p>
    <ul class="pii">{pii_rows}</ul>
    <p class="quote">Raw identifiers were replaced before extraction, verification and decision. The re-identification key stays with the report owner and is never stored with the audit.</p>
  </div>
</div>

<h2>Method and limitations</h2>
<p class="quote">{("This audit used " + str(record.get('usage', {}).get('credits')) + " Clocked credits across five calls. ") if record.get('usage', {}).get('credits') else ""}The regulatory source supplied with this audit is the only authority used for verification. A term is marked <em>not stated</em> when the source is silent; absence of a rule is not evidence of compliance. Deterministic checks are arithmetic and are reported separately from model judgement. This report is decision support, not legal advice.</p>

<h2>Masked document</h2>
<pre>{esc((record.get('document') or {}).get('masked_document') or '')}</pre>

<footer><span>{brand} · AuditTrail AI v2.0</span><span>Protected by Clocked</span></footer>
</div></body></html>"""


def render_json(record: dict[str, Any]) -> str:
    return json.dumps(record, indent=2, ensure_ascii=False, default=str)
