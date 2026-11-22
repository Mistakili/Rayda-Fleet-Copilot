"""Deterministic telemetry loading and querying for the Rayda Fleet Copilot."""
from __future__ import annotations
import json
from math import isfinite
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

@dataclass(frozen=True)
class Snapshot:
    device_id: str
    company_id: str
    employee_id: str
    collected_at: str
    raw: dict[str, Any]

    @property
    def battery(self) -> dict[str, Any] | None:
        value = self.raw.get("battery")
        return value if isinstance(value, dict) else None

    @property
    def disk_volumes(self) -> list[dict[str, Any]]:
        value = self.raw.get("disk_volumes", [])
        return value if isinstance(value, list) else []

    @property
    def compliance_results(self) -> list[dict[str, Any]]:
        value = self.raw.get("compliance_results", [])
        return value if isinstance(value, list) else []

    @property
    def memory(self) -> dict[str, Any]:
        value = self.raw.get("memory", {})
        return value if isinstance(value, dict) else {}


def load_snapshots(path: str | Path) -> list[Snapshot]:
    """Load NDJSON strictly; fail with line context rather than silently skipping data."""
    snapshots: list[Snapshot] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
            required = ("device_id", "company_id", "employee_id", "collected_at")
            missing = [key for key in required if not row.get(key)]
            if missing:
                raise ValueError(f"Missing required fields {missing} on line {line_no}")
            snapshots.append(Snapshot(row["device_id"], row["company_id"], row["employee_id"], row["collected_at"], row))
    return snapshots


def latest_by_device(snapshots: Iterable[Snapshot], company_id: str) -> list[Snapshot]:
    """Return each device's latest snapshot, strictly scoped to one tenant."""
    latest: dict[str, Snapshot] = {}
    for item in snapshots:
        if item.company_id != company_id:
            continue
        if item.device_id not in latest or item.collected_at > latest[item.device_id].collected_at:
            latest[item.device_id] = item
    return sorted(latest.values(), key=lambda x: x.device_id)


def low_disk_devices(snapshots: Iterable[Snapshot], company_id: str, threshold_pct: float = 15.0) -> list[dict[str, Any]]:
    """Find devices whose latest reported volume has <= threshold_pct free space."""
    results = []
    for item in latest_by_device(snapshots, company_id):
        for volume in item.disk_volumes:
            size, available = volume.get("size_bytes"), volume.get("available_bytes")
            if (not isinstance(size, (int, float)) or not isfinite(size) or size <= 0
                    or not isinstance(available, (int, float)) or not isfinite(available)
                    or available < 0 or available > size):
                continue
            free_pct = available / size * 100
            if free_pct <= threshold_pct:
                results.append({"device_id": item.device_id, "company_id": item.company_id,
                                "employee_id": item.employee_id, "collected_at": item.collected_at,
                                "volume": volume.get("volume_name"), "free_pct": round(free_pct, 2),
                                "evidence": {"size_bytes": size, "available_bytes": available}})
    return results


def compliance_failures(snapshots: Iterable[Snapshot], company_id: str, severity: str | None = None) -> list[dict[str, Any]]:
    """Return latest-snapshot compliance failures for a tenant."""
    results = []
    for item in latest_by_device(snapshots, company_id):
        for check in item.compliance_results:
            if check.get("status") == "fail" and (severity is None or check.get("severity") == severity):
                results.append({"device_id": item.device_id, "company_id": item.company_id,
                                "employee_id": item.employee_id, "collected_at": item.collected_at,
                                "check_id": check.get("check_id"), "severity": check.get("severity"),
                                "evidence": check})
    return results


def dataset_profile(snapshots: list[Snapshot]) -> dict[str, Any]:
    devices = {s.device_id for s in snapshots}
    companies = {s.company_id for s in snapshots}
    employees = {s.employee_id for s in snapshots}
    by_device: dict[str, list[Snapshot]] = {}
    for s in snapshots:
        by_device.setdefault(s.device_id, []).append(s)
    return {
        "snapshots": len(snapshots), "devices": len(devices), "companies": len(companies),
        "employees": len(employees), "snapshots_per_device": sorted({len(v) for v in by_device.values()}),
        "start": min(s.collected_at for s in snapshots), "end": max(s.collected_at for s in snapshots),
        "missing_battery": sum("battery" not in s.raw for s in snapshots),
        "missing_network": sum("network" not in s.raw for s in snapshots),
    }


def telemetry_quality_report(snapshots: Iterable[Snapshot], company_id: str | None = None) -> dict[str, Any]:
    """Report telemetry coverage and basic validity; absence is not a failure."""
    rows = [s for s in snapshots if company_id is None or s.company_id == company_id]
    total = len(rows)

    def summary(available: int, invalid: int = 0) -> dict[str, Any]:
        return {
            "available": available,
            "missing": max(total - available - invalid, 0),
            "invalid": invalid,
            "coverage_pct": round(available / total * 100, 1) if total else 0.0,
        }

    battery_present = [s for s in rows if s.battery is not None]
    battery_valid = sum(
        isinstance(s.battery.get("full_charge_capacity"), (int, float))
        and isfinite(s.battery["full_charge_capacity"])
        and s.battery["full_charge_capacity"] > 0
        for s in battery_present
    )
    network_present = sum(isinstance(s.raw.get("network"), list) for s in rows)
    memory_present = [s for s in rows if isinstance(s.raw.get("memory"), dict)]
    memory_valid = sum(
        isinstance(s.memory.get("total_memory_bytes"), (int, float))
        and isfinite(s.memory["total_memory_bytes"]) and s.memory["total_memory_bytes"] > 0
        and isinstance(s.memory.get("used_memory_bytes"), (int, float))
        and isfinite(s.memory["used_memory_bytes"])
        and 0 <= s.memory["used_memory_bytes"] <= s.memory["total_memory_bytes"]
        for s in memory_present
    )
    disk_volumes = [v for s in rows for v in s.disk_volumes]
    valid_volumes = sum(
        isinstance(v.get("size_bytes"), (int, float)) and isfinite(v["size_bytes"]) and v["size_bytes"] > 0
        and isinstance(v.get("available_bytes"), (int, float)) and isfinite(v["available_bytes"])
        and 0 <= v["available_bytes"] <= v["size_bytes"]
        for v in disk_volumes
    )
    compliance_present = sum(isinstance(s.raw.get("compliance_results"), list) for s in rows)
    os_present = sum(isinstance(s.raw.get("os"), dict) and bool(s.raw.get("os")) for s in rows)

    return {
        "company_id": company_id,
        "snapshots": total,
        "fields": {
            "battery_capacity": summary(battery_valid, len(battery_present) - battery_valid),
            "network": summary(network_present),
            "memory_utilization": summary(memory_valid, len(memory_present) - memory_valid),
            "disk_volumes": {
                "reported_volumes": len(disk_volumes),
                "valid_volumes": valid_volumes,
                "invalid_volumes": len(disk_volumes) - valid_volumes,
                "validity_pct": round(valid_volumes / len(disk_volumes) * 100, 1) if disk_volumes else 0.0,
            },
            "compliance_results": summary(compliance_present),
            "os": summary(os_present),
        },
        "notes": [
            "Missing telemetry is unknown, not a compliance failure.",
            "Network coverage measures whether a network field was reported, not network health.",
            "Disk volume counts are volume-level; other coverage counts are snapshot-level.",
        ],
    }
