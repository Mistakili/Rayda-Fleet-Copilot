from fleet_copilot.data import Snapshot
from fleet_copilot.risk import device_attention_register


def snap(device, company="acme-001", day="01", raw=None):
    return Snapshot(device, company, "emp-" + device,
                    f"2026-06-{day}T00:00:00Z", raw or {})


def test_attention_register_is_tenant_scoped_and_sorted():
    rows = [
        snap("quiet", raw={"memory": {"total_memory_bytes": 100, "used_memory_bytes": 20}}),
        snap("alert", raw={"compliance_results": [
            {"check_id": "encryption", "status": "fail", "severity": "high"},
            {"check_id": "screen-lock", "status": "fail", "severity": "medium"},
        ]}),
        snap("other", company="globex-002", raw={"compliance_results": [
            {"check_id": "x", "status": "fail", "severity": "high"}
        ]}),
    ]
    result = device_attention_register(rows, "acme-001")
    assert [x["device_id"] for x in result] == ["alert", "quiet"]
    assert all(x["company_id"] == "acme-001" for x in result)
    assert result[0]["attention_score"] == 50
    assert result[0]["attention_band"] == "high_attention"


def test_missing_telemetry_does_not_increase_attention_score():
    rows = [snap("unknown", raw={})]
    result = device_attention_register(rows, "acme-001")
    assert result[0]["attention_score"] == 0
    assert result[0]["attention_band"] == "assessment_limited"
    assert result[0]["assessment_coverage"]["coverage_pct"] == 0


def test_latest_low_disk_is_an_explainable_current_issue():
    rows = [
        snap("disk", day="01", raw={"disk_volumes": [
            {"volume_name": "C:", "size_bytes": 100, "available_bytes": 50}
        ]}),
        snap("disk", day="02", raw={"disk_volumes": [
            {"volume_name": "C:", "size_bytes": 100, "available_bytes": 10}
        ]}),
    ]
    result = device_attention_register(rows, "acme-001")
    assert result[0]["current_low_disk_volumes"] == 1
    assert result[0]["attention_score"] == 30
    assert result[0]["issues"][0]["source"] == "latest_low_disk"


def test_invalid_measurements_are_not_scored_as_issues():
    rows = [snap("invalid", raw={
        "memory": {"total_memory_bytes": 100, "used_memory_bytes": 150},
        "disk_volumes": [{"volume_name": "C:", "size_bytes": 100, "available_bytes": 101}],
    })]
    result = device_attention_register(rows, "acme-001")
    assert result[0]["attention_score"] == 0
    assert result[0]["attention_band"] == "assessment_limited"
