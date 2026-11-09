from datetime import date

from backend import claims


def test_parse_number_reads_word_numbers():
    assert claims.parse_number("four (4) marked bays") == 4
    assert claims.parse_number("twenty") == 20
    assert claims.parse_number("approximately 220 square meters") == 220


def test_parse_money_detects_currency():
    assert claims.parse_money("USD 3,850 per month") == (3850.0, "USD")
    assert claims.parse_money("$5,000") == (5000.0, "USD")


def test_parse_date_handles_lease_formats():
    assert claims.parse_date("1 October 2026") == date(2026, 10, 1)
    assert claims.parse_date("30 September 2031") == date(2031, 9, 30)
    assert claims.parse_date("01/10/2026") == date(2026, 10, 1)


def _extracted():
    return {
        "floor_area_sqm": {"value": "220 square meters"},
        "parking_bays": {"value": "four (4)"},
        "base_rent": {"value": "USD 3,850 per month"},
        "escalation": {"value": "annual escalation of 4 percent"},
        "lease_start": {"value": "1 October 2026"},
        "lease_end": {"value": "30 September 2031"},
        "permitted_use": {"value": "The Premises shall be used solely for the operation of a specialty coffee roastery and retail cafe."},
        "signage": {"value": "one exterior sign, subject to municipal signage bylaw approval"},
        "assignment_clause": {"value": "Tenant may not assign without consent, which may be withheld in Landlord's sole discretion."},
    }


def test_facts_are_derived():
    facts = claims.derive_facts(_extracted())
    assert facts["area_sqm"] == 220
    assert facts["parking_bays"] == 4
    assert facts["term_years"] == 5.0
    assert facts["escalation_pct"] == 4


def test_roasting_claim_not_duplicated_when_use_clause_mentions_it():
    built = claims.build_claims(_extracted())
    roast_claims = [c for c in built if "roast" in c["text"].lower()]
    assert len(roast_claims) == 1


def test_parking_claim_is_rule_owned():
    built = claims.build_claims(_extracted())
    parking = [c for c in built if "parking bays" in c["text"]]
    assert parking and parking[0]["probe"] is None


def test_answer_is_never_empty():
    assert claims.build_answer(_extracted()).startswith("The submitted lease")
    assert claims.build_answer({}) != ""
