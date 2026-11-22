from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleet_copilot.data import load_snapshots, dataset_profile, latest_by_device, low_disk_devices, compliance_failures

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
