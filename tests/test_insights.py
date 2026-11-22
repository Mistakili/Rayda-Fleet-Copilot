from pathlib import Path
from fleet_copilot.data import load_snapshots
from fleet_copilot.insights import all_insights, battery_insights, memory_insights, storage_insights, compliance_drift_insights

DATA = Path(__file__).parents[1] / "data" / "device-telemetry-dataset.ndjson"


def test_insights_are_tenant_scoped_and_evidence_backed():
    rows = load_snapshots(DATA)
    for detector in (battery_insights, memory_insights, storage_insights, compliance_drift_insights):
        findings = detector(rows, "acme-001")
        assert all(f["company_id"] == "acme-001" for f in findings)
        assert all(f.get("evidence") or f.get("transitions") for f in findings)


def test_all_insights_are_deterministic():
    rows = load_snapshots(DATA)
    assert all_insights(rows, "acme-001") == all_insights(rows, "acme-001")


def test_insights_do_not_mix_companies():
    rows = load_snapshots(DATA)
    acme = all_insights(rows, "acme-001")
    globex = all_insights(rows, "globex-002")
    assert all(x["company_id"] == "acme-001" for x in acme)
    assert all(x["company_id"] == "globex-002" for x in globex)
