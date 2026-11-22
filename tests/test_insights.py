from pathlib import Path
from fleet_copilot.data import Snapshot, load_snapshots
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


def test_missing_and_invalid_telemetry_is_not_counted_as_failure():
    rows = [
        Snapshot("dev-1", "acme-001", "emp-1", "2026-06-01T00:00:00Z", {}),
        Snapshot("dev-1", "acme-001", "emp-1", "2026-06-02T00:00:00Z", {
            "memory": {"total_memory_bytes": 100, "used_memory_bytes": 150},
            "disk_volumes": [{"volume_name": "C:", "size_bytes": 100, "available_bytes": -5}],
        }),
        Snapshot("dev-1", "acme-001", "emp-1", "2026-06-03T00:00:00Z", {
            "memory": {"total_memory_bytes": 100, "used_memory_bytes": 90},
            "disk_volumes": [{"volume_name": "C:", "size_bytes": 100, "available_bytes": 10}],
        }),
    ]
    assert memory_insights(rows, "acme-001") == []
    assert storage_insights(rows, "acme-001") == []


def test_out_of_range_memory_and_storage_measurements_are_handled_safely():
    rows = [
        Snapshot("dev-2", "acme-001", "emp-2", "2026-06-01T00:00:00Z", {
            "memory": {"total_memory_bytes": 100, "used_memory_bytes": 120},
            "disk_volumes": [{"volume_name": "C:", "size_bytes": 100, "available_bytes": 0}],
        }),
        Snapshot("dev-2", "acme-001", "emp-2", "2026-06-02T00:00:00Z", {
            "memory": {"total_memory_bytes": 100, "used_memory_bytes": 120},
            "disk_volumes": [{"volume_name": "C:", "size_bytes": 100, "available_bytes": 0}],
        }),
    ]
    assert memory_insights(rows, "acme-001") == []
    findings = storage_insights(rows, "acme-001")
    assert len(findings) == 1
    assert findings[0]["observations"] == 2
