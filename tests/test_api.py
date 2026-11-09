import pytest
from fastapi.testclient import TestClient

import backend.api as api_module
from backend.clocked import StepResult
from backend.main import app

LEASE = (
    "Commercial lease between Northbridge Property Partners LLC and Verde Coffee Roasters Inc. "
    "The premises is approximately 220 square meters and the tenant is allocated four (4) parking bays. "
    "Live entertainment after 22:00 requires only the landlord's written consent. "
    "Contact: Ms. A. Mwale, finance@verdecoffee.example, +260 97 000 1122."
)
ZONING = (
    "Commercial units must provide a minimum of two (2) parking bays per 100 square meters of floor area. "
    "Live entertainment after 22:00 requires a supplementary entertainment permit. "
    "One exterior sign per frontage is permitted."
)


class FakeGateway:
    available = True

    def protect(self, text):
        return StepResult(
            "protect",
            {
                "entities": [
                    {"type": "organization", "value": "Northbridge Property Partners LLC", "start": 24, "end": 57, "confidence": 1},
                    {"type": "organization", "value": "Verde Coffee Roasters Inc", "start": 62, "end": 87, "confidence": 1},
                ]
            },
            10,
        )

    def guard(self, text):
        return StepResult("guard", {"verdict": "benign", "injection": 0.001}, 10)

    def extract(self, text):
        return StepResult(
            "extract",
            {
                "fields": {
                    "floor_area_sqm": {"value": "220 square meters", "start": 0, "end": 1, "confidence": 1},
                    "parking_bays": {"value": "four (4)", "start": 0, "end": 1, "confidence": 1},
                    "permitted_use": {"value": "coffee roastery with live entertainment after 22:00", "start": 0, "end": 1, "confidence": 1},
                    "signage": {"value": "one exterior sign", "start": 0, "end": 1, "confidence": 1},
                    "assignment_clause": {"value": "no assignment without consent", "start": 0, "end": 1, "confidence": 1},
                }
            },
            10,
        )

    def ground(self, **kwargs):
        return StepResult(
            "verify",
            {
                "verdict": "contradicted",
                "grounded": 0.5,
                "ungrounded": 0.5,
                "claims": [
                    {
                        "claim": "The lease permits live entertainment after 22:00 with consent alone.",
                        "verdict": "contradicted",
                        "weight": 0.5,
                        "contradicted": 0.98,
                        "supported": 0.01,
                        "not_stated": 0.01,
                        "evidence_quote": "requires a supplementary entertainment permit",
                    }
                ],
            },
            10,
        )

    def decide(self, **kwargs):
        return StepResult(
            "decide",
            {
                "answers": {
                    "risk_level": {"value": "HIGH", "probabilities": {"HIGH": 0.9}, "confidence": 0.9},
                    "compliance_risk_detected": {"value": True, "probability": 0.9},
                    "required_actions": {"value": ["legal_review"], "probabilities": {}},
                    "human_review_required": {"value": True, "probability": 0.9},
                }
            },
            10,
        )


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(api_module, "ClockedGateway", FakeGateway)
    return TestClient(app)


def test_health_and_config(client):
    health = client.get("/api/v1/health").json()
    assert health["status"] == "ok"
    assert health["pipeline"] == ["protect", "guard", "extract", "verify", "decide"]
    config = client.get("/api/v1/config").json()
    assert config["demo_mode"] is True
    assert len(config["plans"]) == 4


def test_audit_pipeline_and_persistence(client):
    response = client.post(
        "/api/v1/audit/process",
        json={"document_text": LEASE, "compliance_rules": ZONING, "title": "Test audit"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    audit = body["audit"]
    assert audit["status"] == "success"
    assert audit["risk"]["risk_level"] == "HIGH"
    assert audit["pii"]["entity_count"] == 4
    assert body["reidentification_key"]
    assert "finance@verdecoffee.example" not in audit["document"]["masked_document"]

    listing = client.get("/api/v1/audits").json()
    assert any(a["id"] == audit["id"] for a in listing["audits"])

    detail = client.get(f"/api/v1/audits/{audit['id']}").json()
    assert detail["audit"]["title"] == "Test audit"


def test_quota_is_enforced(client, monkeypatch):
    from backend import billing

    used = client.get("/api/v1/billing/usage").json()["used"]
    monkeypatch.setitem(billing.PLANS["free"], "audits_per_month", used)
    payload = {"document_text": LEASE, "compliance_rules": ZONING, "title": "Quota test"}
    response = client.post("/api/v1/audit/process", json=payload)
    assert response.status_code == 402, response.text
    assert response.json()["detail"]["error"] == "quota_exceeded"


def test_report_exports(client):
    response = client.post(
        "/api/v1/audit/process",
        json={"document_text": LEASE, "compliance_rules": ZONING, "title": "Export test"},
    )
    if response.status_code == 402:  # quota already spent in another test
        pytest.skip("quota exhausted")
    audit_id = response.json()["audit"]["id"]

    md = client.get(f"/api/v1/audits/{audit_id}/report.md")
    assert md.status_code == 200
    assert "Claim-by-claim verification" in md.text
    html = client.get(f"/api/v1/audits/{audit_id}/report.html")
    assert html.status_code == 200
    assert "Deterministic checks" in html.text
    js = client.get(f"/api/v1/audits/{audit_id}/report.json")
    assert js.json()["id"] == audit_id


def test_unknown_audit_is_404(client):
    assert client.get("/api/v1/audits/00000000-0000-4000-8000-000000000000").status_code == 404


def test_validation_rejects_empty_documents(client):
    response = client.post("/api/v1/audit/process", json={"document_text": "short", "compliance_rules": "short"})
    assert response.status_code == 422


def test_api_keys_require_paid_plan_then_authenticate(client):
    # Free plan: issuing a key is refused.
    assert client.get("/api/v1/api-keys").json()["api_access"] is False
    refused = client.post("/api/v1/api-keys", json={"label": "ci"})
    assert refused.status_code == 403

    # Sandbox upgrade, then issue.
    assert client.post("/api/v1/billing/plan", json={"plan": "pro"}).status_code == 200
    created = client.post("/api/v1/api-keys", json={"label": "ci"})
    assert created.status_code == 200
    raw = created.json()["key"]
    assert raw.startswith("at_")

    # The key authenticates the same routes.
    listing = client.get("/api/v1/audits", headers={"X-API-Key": raw})
    assert listing.status_code == 200
    assert client.get("/api/v1/audits", headers={"X-API-Key": "at_wrong"}).status_code == 401
