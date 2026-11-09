from datetime import datetime, timezone

from backend.storage import SQLiteStore


def _record(audit_id="a1", risk="HIGH"):
    return {
        "id": audit_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "Test lease",
        "status": "success",
        "risk": {"risk_level": risk, "score": 80, "claim_stats": {"contradicted": 1}, "rule_stats": {"fail": 2}},
        "timings": {"total_ms": 4200},
    }


def test_roundtrip(tmp_path):
    store = SQLiteStore(tmp_path / "t.db")
    record = _record()
    store.create_audit("user-1", record)

    assert store.get_audit("user-1", "a1")["title"] == "Test lease"
    assert store.get_audit("user-2", "a1") is None  # tenant isolation


def test_list_is_scoped_and_newest_first(tmp_path):
    store = SQLiteStore(tmp_path / "t.db")
    store.create_audit("user-1", _record("a1"))
    store.create_audit("user-1", {**_record("a2"), "created_at": "2030-01-01T00:00:00+00:00"})
    store.create_audit("user-2", _record("b1"))

    rows = store.list_audits("user-1")
    assert [r["id"] for r in rows] == ["a2", "a1"]
    assert rows[0]["risk_level"] == "HIGH"


def test_count_since(tmp_path):
    store = SQLiteStore(tmp_path / "t.db")
    store.create_audit("user-1", _record("a1"))
    assert store.count_audits_since("user-1", "2000-01-01T00:00:00+00:00") == 1
    assert store.count_audits_since("user-1", "2999-01-01T00:00:00+00:00") == 0


def test_profile_defaults_to_free(tmp_path):
    store = SQLiteStore(tmp_path / "t.db")
    profile = store.get_profile("user-1")
    assert profile["plan"] == "free"
    updated = store.upsert_profile("user-1", plan="firm", org_name="Harbor Legal")
    assert updated["plan"] == "firm"
    assert store.get_profile("user-1")["org_name"] == "Harbor Legal"


def test_leads(tmp_path):
    store = SQLiteStore(tmp_path / "t.db")
    store.add_lead("a@b.com", "Acme", "demo")
    with store._connect() as conn:
        assert conn.execute("select count(*) from leads").fetchone()[0] == 1
