from backend.rules import evaluate

ZONING = """
Section 4B - Ground-floor commercial use. Retail and food and beverage preparation permitted.
Section 4B.2 - Food roasting and baking. Roasting is permitted when (a) the process area does not exceed 30 percent of total floor area;
(b) a mechanical ventilation system approved by the municipal fire authority is installed.
Section 7C - Entertainment. Live entertainment after 22:00 requires a supplementary entertainment permit from the District Licensing Board;
the landlord's consent alone is not sufficient.
Section 9A - Signage. One exterior sign per street frontage is permitted, with a maximum face area of 3 square meters.
Section 9D - Service bays. Delivery vehicles may use designated service bays between 05:00 and 11:00.
Section 12 - Assignment. A "sole discretion" landlord consent clause is lawful and does not require amendment.
Section 15 - Parking allocations. Commercial units must provide a minimum of two (2) parking bays per 100 square meters of floor area.
"""

LEASE = """
The Premises comprises approximately 220 square meters. Tenant is allocated four (4) marked bays.
Tenant may not operate a bar, nightclub, or any business involving live entertainment after 22:00 without Landlord's prior written consent.
Tenant may install one exterior sign, subject to municipal signage bylaw approval.
Tenant's delivery vehicles may use the service bay between 05:00 and 11:00 only.
Tenant may not assign this Lease without Landlord's prior written consent, which may be withheld in Landlord's sole discretion.
Tenant's roasting equipment requires a dedicated ventilation system and a grease-interceptor.
"""

EXTRACTED = {
    "floor_area_sqm": {"value": "220 square meters"},
    "parking_bays": {"value": "four (4)"},
    "permitted_use": {"value": "specialty coffee roastery and retail cafe, including on-site roasting, and no live entertainment after 22:00 without landlord consent"},
    "signage": {"value": "one exterior sign, subject to municipal signage bylaw approval"},
    "assignment_clause": {"value": "Tenant may not assign without Landlord's prior written consent, which may be withheld in Landlord's sole discretion."},
}


def findings():
    return {f.id: f for f in evaluate(LEASE, ZONING, EXTRACTED)}


def test_parking_shortfall_is_computed_not_guessed():
    parking = findings()["parking-ratio"]
    assert parking.status == "fail"
    assert parking.severity == "high"
    assert "5 required vs 4 allocated" in parking.computation
    assert "Shortfall of 1" in parking.detail


def test_entertainment_permit_conflict():
    rule = findings()["entertainment-permit"]
    assert rule.status == "fail"
    assert "supplementary entertainment permit" in (rule.evidence_quote or "")


def test_roasting_area_is_review_when_not_stated():
    rule = findings()["roasting-area"]
    assert rule.status == "review"
    assert "does not state the process area" in rule.detail


def test_signage_size_is_review_when_not_stated():
    rule = findings()["signage-area"]
    assert rule.status == "review"


def test_delivery_window_passes_when_identical():
    rule = findings()["delivery-window"]
    assert rule.status == "pass"


def test_assignment_clause_passes_when_lawful():
    rule = findings()["assignment-consent"]
    assert rule.status == "pass"


def test_rules_are_ordered_by_severity():
    severities = [f.severity for f in evaluate(LEASE, ZONING, EXTRACTED)]
    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    assert severities == sorted(severities, key=lambda s: order[s])
