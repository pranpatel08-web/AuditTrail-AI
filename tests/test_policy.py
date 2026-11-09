from backend.policy import assess
from backend.rules import RuleFinding

EXTRACTED = {name: {"value": "x"} for name in ["tenant", "landlord", "premises_address", "lease_start", "lease_end", "base_rent", "permitted_use", "assignment_clause"]}


def claim(verdict, weight=0.2, contradicted=0.0):
    return {"claim": "c", "verdict": verdict, "weight": weight, "contradicted": contradicted}


def rule(status, severity, action=None):
    return RuleFinding(id="r", title="Rule", status=status, severity=severity, detail="d", action=action)


def test_rule_failure_escalates_medium_model_to_high():
    result = assess(
        grounding={"claims": [claim("supported")]},
        rule_findings=[rule("fail", "high", "legal_review")],
        decide={"risk_level": {"value": "MEDIUM", "probabilities": {}}, "compliance_risk_detected": {"probability": 0.4}},
        extracted=EXTRACTED,
    )
    assert result["risk_level"] == "HIGH"
    assert result["escalated"] is True
    assert "legal_review" in result["required_actions"]


def test_clean_audit_is_low():
    result = assess(
        grounding={"claims": [claim("supported")]},
        rule_findings=[rule("pass", "none")],
        decide={"risk_level": {"value": "LOW", "probabilities": {}}, "compliance_risk_detected": {"probability": 0.05}},
        extracted=EXTRACTED,
    )
    assert result["risk_level"] == "LOW"
    assert result["score"] < 25


def test_missing_fields_add_documentation_risk():
    result = assess(
        grounding={"claims": []},
        rule_findings=[],
        decide={"risk_level": {"value": "LOW", "probabilities": {}}},
        extracted={},
    )
    assert result["risk_level"] in {"LOW", "MEDIUM"}
    assert result["missing_fields"]


def test_score_is_bounded():
    result = assess(
        grounding={"claims": [claim("contradicted", 1.0, 0.99) for _ in range(5)]},
        rule_findings=[rule("fail", "high") for _ in range(5)],
        decide={"risk_level": {"value": "HIGH"}, "compliance_risk_detected": {"probability": 1.0}},
        extracted={},
    )
    assert 0 <= result["score"] <= 100
    assert result["risk_level"] == "HIGH"
    assert result["human_review_required"]["value"] is True


def test_low_risk_gets_none_action():
    result = assess(
        grounding={"claims": []},
        rule_findings=[],
        decide={"risk_level": {"value": "LOW"}, "required_actions": {"value": []}},
        extracted=EXTRACTED,
    )
    assert result["required_actions"] == ["none"]
