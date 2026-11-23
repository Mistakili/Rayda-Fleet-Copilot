"""Bounded fleet agent with deterministic and optional LLM planning."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .data import Snapshot, low_disk_devices, compliance_failures
from .insights import (
    battery_insights, memory_insights, storage_insights, compliance_drift_insights,
)

ALLOWED_TOOLS = {
    "low_disk", "compliance_failures", "battery_trends",
    "ram_trends", "storage_trends", "compliance_drift",
}


class Planner(Protocol):
    def plan(self, question: str, max_steps: int) -> list[str]: ...


@dataclass
class AgentState:
    question: str
    company_id: str
    plan: list[str] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    planner_mode: str = "deterministic"
    planner_error: str | None = None


class FleetTools:
    def __init__(self, snapshots: list[Snapshot]):
        self.snapshots = snapshots

    def execute(self, name: str, company_id: str) -> dict[str, Any]:
        # Every tool receives trusted company scope from the application context.
        if name == "low_disk":
            data = low_disk_devices(self.snapshots, company_id)
        elif name == "compliance_failures":
            data = compliance_failures(self.snapshots, company_id)
        elif name == "battery_trends":
            data = battery_insights(self.snapshots, company_id)
        elif name == "ram_trends":
            data = memory_insights(self.snapshots, company_id)
        elif name == "storage_trends":
            data = storage_insights(self.snapshots, company_id)
        elif name == "compliance_drift":
            data = compliance_drift_insights(self.snapshots, company_id)
        else:
            raise ValueError(f"Tool not allowed: {name}")
        return {"tool": name, "company_id": company_id, "count": len(data), "results": data}


class FleetAgent:
    """LLM-assisted intent planning with deterministic, tenant-scoped execution."""
    def __init__(self, snapshots: list[Snapshot], max_steps: int = 4, planner: Planner | None = None):
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.tools = FleetTools(snapshots)
        self.max_steps = max_steps
        self.planner = planner

    def plan(self, question: str) -> list[str]:
        q = question.lower()
        plan = []
        if any(k in q for k in ("disk", "storage", "space")):
            plan.append("low_disk")
        if any(k in q for k in ("compliance", "compliant", "screen lock", "encryption")):
            plan.append("compliance_failures")
        if any(k in q for k in ("battery", "capacity")):
            plan.append("battery_trends")
        if any(k in q for k in ("ram", "memory")):
            plan.append("ram_trends")
        if any(k in q for k in ("trend", "persistent", "insight", "history")):
            plan.extend([
                "battery_trends", "ram_trends", "storage_trends", "compliance_drift"
            ])
        if not plan:
            plan = ["low_disk", "compliance_failures"]
        return list(dict.fromkeys(plan))[:self.max_steps]

    def _validated_plan(self, question: str) -> list[str]:
        if self.planner is None:
            return self.plan(question)
        try:
            proposed = self.planner.plan(question, self.max_steps)
            if not isinstance(proposed, list) or not proposed:
                raise ValueError("Planner returned an empty or invalid tool plan")
            if any(not isinstance(name, str) or name not in ALLOWED_TOOLS for name in proposed):
                raise ValueError("Planner requested a tool outside the allowlist")
            return list(dict.fromkeys(proposed))[:self.max_steps]
        except Exception as exc:
            # A model outage or invalid response must not stop the deterministic demo.
            self._planner_error = f"{type(exc).__name__}: {exc}"
            return self.plan(question)

    def invoke(self, question: str, authenticated_company_id: str) -> AgentState:
        if not authenticated_company_id:
            raise ValueError("Authenticated company context is required")
        self._planner_error = None
        state = AgentState(question=question, company_id=authenticated_company_id)
        state.plan = self._validated_plan(question)
        if self.planner is not None and self._planner_error is None:
            state.planner_mode = "llm"
        elif self.planner is not None:
            state.planner_mode = "deterministic_fallback"
            state.planner_error = self._planner_error

        # Company scope is injected by the application, never supplied by the model.
        for index, tool_name in enumerate(state.plan, start=1):
            observation = self.tools.execute(tool_name, authenticated_company_id)
            state.observations.append(observation)
            state.steps.append({
                "step": index,
                "decision": f"Call {tool_name}",
                "observation_count": observation["count"],
            })

        state.answer = _summarize_investigation(
            question, authenticated_company_id, state.observations
        )
        return state


def _summarize_investigation(
    question: str, company_id: str, observations: list[dict[str, Any]]
) -> str:
    """Turn deterministic tool evidence into a concise, question-aware summary."""
    findings = [
        (observation["tool"], finding)
        for observation in observations
        for finding in observation.get("results", [])
    ]
    if not findings:
        checked = ", ".join(obs["tool"].replace("_", " ") for obs in observations) or "no tools"
        return (
            f"No matching findings were returned for {company_id}. "
            f"Investigation checked {checked}. This means no configured detector crossed "
            "its current threshold; it is not proof that every device is healthy."
        )

    lines = [f"{len(findings)} finding(s) across {len({item.get('device_id') for _, item in findings if item.get('device_id')})} device(s) for {company_id}."]
    asks_about_trend = any(word in question.lower() for word in ("trend", "worse", "worsening", "improving", "over time", "history", "historical"))

    for tool, item in findings[:6]:
        device = item.get("device_id")
        prefix = f"{device}: " if device else ""
        finding_type = item.get("type", tool).replace("_", " ")
        detail = item.get("finding") or item.get("explanation") or "A configured fleet indicator was detected."
        line = f"{prefix}{detail}"

        trend = item.get("trend")
        if trend and isinstance(trend.get("change"), (int, float)):
            change = float(trend["change"])
            metric = str(trend.get("metric", "metric")).replace("_", " ")
            start = trend.get("start_value")
            end = trend.get("end_value")
            observations_count = trend.get("observations", "available")
            unit = " percentage points" if metric == "ram utilization pct" else ""
            if abs(change) < 3:
                direction = "remained broadly stable"
            elif change > 0:
                direction = "increased"
            else:
                direction = "decreased"
            line += (
                f" Start-to-end {metric} {direction} from {start} to {end}"
                f" ({change:+.2f}{unit}) across {observations_count} valid observations."
            )
            if asks_about_trend and metric == "ram utilization pct":
                if change > 3:
                    line += " This indicates a worsening start-to-end RAM utilisation trend."
                elif change < -3:
                    line += " This indicates an improving start-to-end RAM utilisation trend."
                else:
                    line += " The readings do not show a material start-to-end increase."
        elif asks_about_trend and finding_type == "persistent ram pressure":
            line += " Persistence is confirmed, but this result does not contain enough trend data to determine whether utilisation is worsening."

        quality = item.get("evidence_quality", {})
        if quality.get("level"):
            line += f" Evidence volume: {quality['level']} ({quality.get('valid_observations', 'n/a')} valid observations)."
        lines.append(line)

    if len(findings) > 6:
        lines.append(f"{len(findings) - 6} additional finding(s) are available in the evidence tables.")
    lines.append("Assessment is based on the selected company's available telemetry; missing measurements are not treated as failures. Review source evidence before taking action.")
    return "\n\n".join(lines)
