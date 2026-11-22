from pathlib import Path
from fleet_copilot.data import load_snapshots
from fleet_copilot.agent import FleetAgent
from fleet_copilot.evals import run_evaluations
import pytest

DATA = Path(__file__).parents[1] / "data" / "device-telemetry-dataset.ndjson"


def test_agent_plans_and_scopes_tools():
    state = FleetAgent(load_snapshots(DATA)).invoke("Show compliance failures", "acme-001")
    assert "compliance_failures" in state.plan
    assert state.steps
    assert all(x["company_id"] == "acme-001" for x in state.observations)


def test_agent_requires_tenant():
    with pytest.raises(ValueError):
        FleetAgent(load_snapshots(DATA)).invoke("disk", "")


def test_broad_history_question_runs_all_four_historical_detectors():
    agent = FleetAgent(load_snapshots(DATA))
    plan = agent.plan("Give me a full fleet history and trend review")
    assert plan == [
        "battery_trends", "ram_trends", "storage_trends", "compliance_drift"
    ]
    state = agent.invoke("Give me a full fleet history and trend review", "acme-001")
    assert [step["decision"] for step in state.steps] == [
        "Call battery_trends", "Call ram_trends",
        "Call storage_trends", "Call compliance_drift"
    ]
    assert all(item["company_id"] == "acme-001" for item in state.observations)


def test_agent_respects_custom_step_bound():
    agent = FleetAgent(load_snapshots(DATA), max_steps=2)
    assert len(agent.plan("full fleet history trend review")) == 2


def test_agent_rejects_invalid_step_bound():
    with pytest.raises(ValueError, match="at least 1"):
        FleetAgent([], max_steps=0)


def test_regression_evaluations_pass():
    assert all(x["passed"] for x in run_evaluations(DATA))
