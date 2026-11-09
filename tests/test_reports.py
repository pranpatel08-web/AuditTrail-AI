from backend.reports import render_html, render_markdown

RECORD = {
    "id": "d05749a7-b42b-4705-bad5-b6635627e9ab",
    "created_at": "2026-11-09T22:26:00+00:00",
    "title": "412 Harbor Street",
    "status": "success",
    "risk": {
        "risk_level": "HIGH",
        "score": 100,
        "headline": "Do not execute without remediation",
        "rationale": ["1 claim contradicted", "Parking shortfall"],
        "required_actions": ["legal_review"],
        "action_labels": {"legal_review": "Route to counsel"},
        "claim_stats": {"contradicted": 1, "supported": 2},
        "rule_stats": {"fail": 2},
    },
    "claims": [
        {
            "claim": "Live entertainment after 22:00 with consent alone.",
            "verdict": "contradicted",
            "evidence_quote": "requires a supplementary entertainment permit",
        }
    ],
    "rules": [
        {
            "title": "Minimum parking allocation",
            "status": "fail",
            "computation": "ceil(220 ÷ 100 × 2) = 5 required vs 4 allocated",
            "evidence_quote": "two parking bays per 100 square meters",
            "detail": "shortfall",
        }
    ],
    "extracted": {"tenant": {"value": "[ORG_1]"}},
    "pii": {"entity_count": 6, "mentions": 6, "counts": {"organization": 2, "email": 1}},
    "document": {"masked_document": "The lease between [ORG_1] and [ORG_2]."},
}


def test_markdown_has_all_sections():
    md = render_markdown(RECORD)
    for heading in ["Outcome", "Claim-by-claim verification", "Deterministic checks", "Privacy handling", "Method and limitations"]:
        assert heading in md
    assert "ceil(220 ÷ 100 × 2)" in md
    assert "Route to counsel" in md


def test_html_is_standalone_and_escaped():
    record = {**RECORD, "title": "Lease <script>alert(1)</script>"}
    html = render_html(record)
    assert html.startswith("<!doctype html>")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "print" in html


def test_white_label_replaces_brand():
    html = render_html(RECORD, org_name="Harbor Legal")
    assert "Harbor Legal" in html
