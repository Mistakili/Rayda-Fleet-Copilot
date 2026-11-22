"""Deterministic telemetry loading and querying for the Rayda Fleet Copilot."""
from __future__ import annotations
import json
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
            if not isinstance(size, (int, float)) or size <= 0 or not isinstance(available, (int, float)):
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
