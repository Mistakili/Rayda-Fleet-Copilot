"""Explicit, bounded tool-using agent loop. LLM-independent core for reproducibility."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .data import Snapshot, low_disk_devices, compliance_failures
from .insights import battery_insights, memory_insights, storage_insights, compliance_drift_insights

@dataclass
class AgentState:
    question: str
    company_id: str
    plan: list[str] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""

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
    """A deterministic planner + explicit tool loop; no model/API key required."""
    def __init__(self, snapshots: list[Snapshot], max_steps: int = 3):
        self.tools = FleetTools(snapshots)
        self.max_steps = max_steps
    def plan(self, question: str) -> list[str]:
        q = question.lower()
        plan=[]
        if any(k in q for k in ("disk", "storage", "space")): plan.append("low_disk")
        if any(k in q for k in ("compliance", "compliant", "screen lock", "encryption")): plan.append("compliance_failures")
        if any(k in q for k in ("battery", "capacity")): plan.append("battery_trends")
        if any(k in q for k in ("ram", "memory")): plan.append("ram_trends")
        if any(k in q for k in ("trend", "persistent", "insight", "history")):
            plan += ["battery_trends","ram_trends","storage_trends","compliance_drift"]
        if not plan: plan=["low_disk","compliance_failures"]
        return list(dict.fromkeys(plan))[:self.max_steps]
    def invoke(self, question: str, authenticated_company_id: str) -> AgentState:
        if not authenticated_company_id: raise ValueError("Authenticated company context is required")
        state=AgentState(question=question, company_id=authenticated_company_id)
        state.plan=self.plan(question)
        # Explicit observe/act loop with bounded steps and recorded tool trace.
        for index, tool_name in enumerate(state.plan, start=1):
            observation=self.tools.execute(tool_name, authenticated_company_id)
            state.observations.append(observation)
            state.steps.append({"step":index,"decision":f"Call {tool_name}","observation_count":observation["count"]})
        total=sum(x["count"] for x in state.observations)
        sections=[]
        for obs in state.observations:
            sections.append(f'{obs["tool"]}: {obs["count"]} finding(s)')
        state.answer=(f"I checked company {authenticated_company_id} using {len(state.steps)} tool call(s). "
                      f"{total} result(s) returned. " + "; ".join(sections) +
                      ". Results are scoped to the authenticated company. Review the evidence records before taking action.")
        return state
