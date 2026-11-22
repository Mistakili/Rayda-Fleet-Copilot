"""Deterministic regression evaluations with dataset-grounded expectations."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent import FleetAgent
from .data import load_snapshots


# Expected counts are regression baselines for the supplied assessment dataset.
# If the source dataset changes, review the evidence and deliberately update these.
_CASES = [
    {"id": "acme_latest_low_disk", "question": "Which devices have low disk space?",
     "company_id": "acme-001", "expected_tool": "low_disk", "expected_count": 2},
    {"id": "globex_latest_compliance_failures", "question": "Show compliance failures",
     "company_id": "globex-002", "expected_tool": "compliance_failures", "expected_count": 6},
    {"id": "initech_battery_history", "question": "What battery trends exist?",
     "company_id": "initech-003", "expected_tool": "battery_trends", "expected_count": 0},
    {"id": "acme_persistent_ram_pressure", "question": "Find persistent memory pressure",
     "company_id": "acme-001", "expected_tool": "ram_trends", "expected_count": 1},
]


def _result_tenant_violations(value: Any, company_id: str) -> int:
    """Count foreign tenant IDs anywhere in nested tool result payloads."""
    violations = 0
    if isinstance(value, dict):
        if "company_id" in value and value["company_id"] != company_id:
            violations += 1
        for child in value.values():
            violations += _result_tenant_violations(child, company_id)
    elif isinstance(value, list):
        for child in value:
            violations += _result_tenant_violations(child, company_id)
    return violations


def run_evaluations(dataset: str | Path) -> list[dict[str, Any]]:
    """Run intent, exact-count, and nested tenant-isolation regression checks."""
    snapshots = load_snapshots(dataset)
    agent = FleetAgent(snapshots)
    results: list[dict[str, Any]] = []

    for case in _CASES:
        state = agent.invoke(case["question"], case["company_id"])
        matching = [obs for obs in state.observations if obs["tool"] == case["expected_tool"]]
        actual_count = matching[0]["count"] if matching else None
        tenant_violations = _result_tenant_violations(state.observations, case["company_id"])
        checks = {
            "expected_tool_selected": case["expected_tool"] in state.plan,
            "expected_count_matches": actual_count == case["expected_count"],
            "all_observations_scoped": all(
                obs["company_id"] == case["company_id"] for obs in state.observations
            ),
            "nested_results_scoped": tenant_violations == 0,
        }
        results.append({
            "id": case["id"], "question": case["question"],
            "company_id": case["company_id"], "passed": all(checks.values()),
            "checks": checks, "expected_tool": case["expected_tool"],
            "expected_count": case["expected_count"], "actual_count": actual_count,
            "tenant_violations": tenant_violations, "plan": state.plan,
            "tool_calls": len(state.steps),
        })
    return results
