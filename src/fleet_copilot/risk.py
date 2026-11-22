"""Explainable, tenant-scoped device attention ranking.

Scores are prototype triage heuristics, not Rayda policy or predictive risk.
Missing telemetry affects assessment coverage only; it never adds risk points.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from .data import Snapshot, compliance_failures, latest_by_device, low_disk_devices
from .insights import all_insights


def _valid_memory(snapshot: Snapshot) -> bool:
    total = snapshot.memory.get("total_memory_bytes")
    used = snapshot.memory.get("used_memory_bytes")
    return (
        isinstance(total, (int, float)) and isfinite(total) and total > 0
        and isinstance(used, (int, float)) and isfinite(used)
        and 0 <= used <= total
    )


def _valid_disk_volume(volume: dict[str, Any]) -> bool:
    size, available = volume.get("size_bytes"), volume.get("available_bytes")
    return (
        isinstance(size, (int, float)) and isfinite(size) and size > 0
        and isinstance(available, (int, float)) and isfinite(available)
        and 0 <= available <= size
    )


def _coverage(history: list[Snapshot]) -> dict[str, Any]:
    """Coverage across six snapshot-level signals; volume validity is per volume."""
    total = len(history)
    checks = {
        "battery_capacity": sum(
            s.battery is not None
            and isinstance(s.battery.get("full_charge_capacity"), (int, float))
            and isfinite(s.battery["full_charge_capacity"])
            and s.battery["full_charge_capacity"] > 0
            for s in history
        ),
        "network_reported": sum(isinstance(s.raw.get("network"), list) for s in history),
        "memory_valid": sum(_valid_memory(s) for s in history),
        "disk_reported": sum(bool(s.disk_volumes) for s in history),
        "compliance_reported": sum(isinstance(s.raw.get("compliance_results"), list) for s in history),
        "os_reported": sum(isinstance(s.raw.get("os"), dict) and bool(s.raw.get("os")) for s in history),
    }
    possible = total * len(checks)
    reported = sum(checks.values())
    return {
        "snapshots": total,
        "signals": checks,
        "coverage_pct": round(reported / possible * 100, 1) if possible else 0.0,
        "method": "Valid/reported signal observations divided by six signals across available device snapshots.",
    }


def device_attention_register(
    snapshots: Iterable[Snapshot], company_id: str, low_disk_threshold_pct: float = 15.0
) -> list[dict[str, Any]]:
    """Rank devices for human review using latest state and historical indicators."""
    rows = list(snapshots)
    latest = latest_by_device(rows, company_id)
    histories: dict[str, list[Snapshot]] = {}
    for item in rows:
        if item.company_id == company_id:
            histories.setdefault(item.device_id, []).append(item)

    current_disk = low_disk_devices(rows, company_id, low_disk_threshold_pct)
    current_compliance = compliance_failures(rows, company_id)
    history_findings = all_insights(rows, company_id)
    disk_by_device: dict[str, list[dict[str, Any]]] = {}
    compliance_by_device: dict[str, list[dict[str, Any]]] = {}
    history_by_device: dict[str, list[dict[str, Any]]] = {}
    for item in current_disk:
        disk_by_device.setdefault(item["device_id"], []).append(item)
    for item in current_compliance:
        compliance_by_device.setdefault(item["device_id"], []).append(item)
    for finding in history_findings:
        device_id = finding.get("device_id")
        if device_id:
            history_by_device.setdefault(device_id, []).append(finding)

    register = []
    for snapshot in latest:
        device_id = snapshot.device_id
        disk = disk_by_device.get(device_id, [])
        failures = compliance_by_device.get(device_id, [])
        historical = history_by_device.get(device_id, [])
        issues: list[dict[str, Any]] = []
        score = 0

        if failures:
            # Severity is preserved from source data; points only order this prototype's queue.
            severity_points = {"high": 30, "medium": 20, "low": 10}
            points = sum(severity_points.get(str(x.get("severity", "")).lower(), 10) for x in failures)
            score += min(points, 60)
            issues.append({"source": "latest_compliance", "count": len(failures),
                           "points": min(points, 60),
                           "details": [{"check_id": x.get("check_id"), "severity": x.get("severity")} for x in failures]})
        if disk:
            points = min(20 * len(disk), 40)
            score += points
            issues.append({"source": "latest_low_disk", "count": len(disk), "points": points,
                           "details": [{"volume": x.get("volume"), "free_pct": x.get("free_pct")} for x in disk]})

        historical_points = {
            "battery_capacity_decline": 10,
            "persistent_ram_pressure": 15,
            "persistent_low_storage": 10,
            "compliance_drift": 10,
        }
        for finding in historical:
            points = historical_points.get(finding["type"], 0)
            if points:
                score += points
                issues.append({"source": finding["type"], "count": 1, "points": points,
                               "evidence_quality": finding.get("evidence_quality", {}).get("level", "unknown"),
                               "finding": finding.get("finding")})

        score = min(score, 100)
        if score >= 50:
            band = "high_attention"
        elif score >= 25:
            band = "elevated_attention"
        elif score > 0:
            band = "review"
        else:
            band = "no_detected_issue"

        coverage = _coverage(histories.get(device_id, [snapshot]))
        if score == 0 and coverage["coverage_pct"] < 60:
            band = "assessment_limited"

        register.append({
            "device_id": device_id,
            "company_id": company_id,
            "employee_id": snapshot.employee_id,
            "latest_snapshot_at": snapshot.collected_at,
            "attention_score": score,
            "attention_band": band,
            "current_compliance_failures": len(failures),
            "current_low_disk_volumes": len(disk),
            "historical_indicator_count": len(historical),
            "issues": issues,
            "assessment_coverage": coverage,
        })

    order = {"high_attention": 0, "elevated_attention": 1, "review": 2,
             "assessment_limited": 3, "no_detected_issue": 4}
    return sorted(register, key=lambda x: (order[x["attention_band"]], -x["attention_score"], x["device_id"]))
