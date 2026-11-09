from backend.pseudonym import pseudonymise

LEASE = (
    'This Lease is between Northbridge Property Partners LLC ("Landlord") and '
    'Verde Coffee Roasters Inc. ("Tenant"). Tenant contact: Ms. A. Mwale, '
    "finance@verdecoffee.example, +260 97 000 1122, 412 Harbor Street, Suite 100."
)


def _entities():
    def span(kind, value):
        start = LEASE.index(value)
        return {"type": kind, "value": value, "start": start, "end": start + len(value), "confidence": 1}

    return [
        span("organization", "Northbridge Property Partners LLC"),
        span("organization", "Verde Coffee Roasters Inc"),
        span("person", "Tenant"),
        span("person", "Ms. A. Mwale"),
    ]


def test_role_terms_are_not_masked():
    result = pseudonymise(LEASE, _entities())
    assert "Tenant" not in result.vault.values()
    assert "Tenant" in result.text
    assert "Tenant conta" in result.text


def test_same_entity_gets_same_token_and_distinct_entities_differ():
    result = pseudonymise(LEASE, _entities())
    assert "[ORG_1]" in result.text
    assert "[ORG_2]" in result.text
    orgs = [token for token, value in result.vault.items() if value.startswith(("Northbridge", "Verde"))]
    assert len(set(orgs)) == 2


def test_regex_backstops_catch_contact_details():
    result = pseudonymise(LEASE, [])
    assert "[EMAIL_1]" in result.text
    assert "[PHONE_1]" in result.text
    assert "finance@verdecoffee.example" not in result.text
    assert "+260 97 000 1122" not in result.text


def test_offsets_point_at_tokens():
    result = pseudonymise(LEASE, _entities())
    for finding in result.findings:
        assert result.text[finding.start : finding.end] == f"[{finding.token}]"


def test_fragments_are_merged():
    text = "Tenant: Verde Coffee Roasters Inc. shall pay."
    entities = [
        {"type": "organization", "value": "Verde Coffee", "start": 8, "end": 20},
        {"type": "organization", "value": "Roasters Inc", "start": 21, "end": 33},
    ]
    result = pseudonymise(text, entities)
    assert result.entity_count == 1
    assert "[ORG_1]" in result.text


def test_vault_never_contains_role_words():
    result = pseudonymise(LEASE, _entities())
    assert "Tenant" not in result.vault.values()
