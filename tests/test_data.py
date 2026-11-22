from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleet_copilot.data import Snapshot, load_snapshots, dataset_profile, latest_by_device, low_disk_devices, compliance_failures, telemetry_quality_report

DATA = Path(__file__).resolve().parents[1] / "data" / "device-telemetry-dataset.ndjson"

def test_dataset_profile():
    rows = load_snapshots(DATA)
    profile = dataset_profile(rows)
    assert profile["snapshots"] == 750
    assert profile["devices"] == 25
    assert profile["companies"] == 3
    assert profile["employees"] == 14
    assert profile["snapshots_per_device"] == [30]
    assert profile["missing_battery"] == 100
    assert profile["missing_network"] == 16

def test_tenant_scope_is_enforced_by_query_functions():
    rows = load_snapshots(DATA)
    acme = latest_by_device(rows, "acme-001")
    assert len(acme) == 10
    assert all(x.company_id == "acme-001" for x in acme)
    assert len(latest_by_device(rows, "not-a-real-tenant")) == 0

def test_compliance_and_disk_tools_are_deterministic_and_scoped():
    rows = load_snapshots(DATA)
    failures = compliance_failures(rows, "acme-001", "high")
    assert all(x["company_id"] == "acme-001" for x in failures)
    low_disk = low_disk_devices(rows, "acme-001")
    assert all(x["company_id"] == "acme-001" for x in low_disk)



def test_low_disk_ignores_non_finite_and_impossible_measurements():
    rows = [
        Snapshot("dev-1", "acme-001", "emp-1", "2026-06-01T00:00:00Z", {
            "disk_volumes": [
                {"volume_name": "nan", "size_bytes": 100, "available_bytes": float("nan")},
                {"volume_name": "infinite", "size_bytes": 100, "available_bytes": float("inf")},
                {"volume_name": "negative", "size_bytes": 100, "available_bytes": -1},
                {"volume_name": "overfull", "size_bytes": 100, "available_bytes": 101},
                {"volume_name": "valid", "size_bytes": 100, "available_bytes": 5},
            ]
        })
    ]
    findings = low_disk_devices(rows, "acme-001")
    assert len(findings) == 1
    assert findings[0]["volume"] == "valid"


def test_telemetry_quality_report_distinguishes_missing_and_invalid():
    rows = load_snapshots(DATA)
    report = telemetry_quality_report(rows)
    assert report["snapshots"] == 750
    assert report["fields"]["battery_capacity"]["missing"] == 100
    assert report["fields"]["battery_capacity"]["available"] == 650
    assert report["fields"]["network"]["missing"] == 16
    assert report["fields"]["memory_utilization"]["available"] == 750
    assert report["fields"]["disk_volumes"]["valid_volumes"] == 750
    assert "Missing telemetry is unknown, not a compliance failure." in report["notes"]


def test_telemetry_quality_report_can_be_tenant_scoped():
    rows = load_snapshots(DATA)
    report = telemetry_quality_report(rows, "acme-001")
    assert report["company_id"] == "acme-001"
    assert report["snapshots"] == 300
    assert report["fields"]["battery_capacity"]["missing"] == 37
