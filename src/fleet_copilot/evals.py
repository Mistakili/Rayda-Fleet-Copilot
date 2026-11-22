"""Small deterministic regression evaluation set."""
from .agent import FleetAgent
from .data import load_snapshots
from pathlib import Path

def run_evaluations(dataset: str | Path) -> list[dict]:
    snapshots=load_snapshots(dataset)
    agent=FleetAgent(snapshots)
    cases=[
        ("Which devices have low disk space?", "acme-001", "low_disk"),
        ("Show compliance failures", "globex-002", "compliance_failures"),
        ("What battery trends exist?", "initech-003", "battery_trends"),
        ("Find persistent memory pressure", "acme-001", "ram_trends"),
    ]
    results=[]
    for question, tenant, expected_tool in cases:
        state=agent.invoke(question, tenant)
        passed=expected_tool in state.plan and all(o["company_id"]==tenant for o in state.observations)
        results.append({"question":question,"company_id":tenant,"passed":passed,
                        "plan":state.plan,"tool_calls":len(state.steps)})
    return results
