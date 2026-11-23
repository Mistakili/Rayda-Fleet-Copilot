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


def test_regression_evaluations_pass_with_expected_counts_and_isolation():
    results = run_evaluations(DATA)
    assert len(results) == 4
    assert all(result["passed"] for result in results)
    assert [result["actual_count"] for result in results] == [2, 6, 0, 1]
    assert all(result["tenant_violations"] == 0 for result in results)
    assert all(all(result["checks"].values()) for result in results)


def test_regression_evaluation_exposes_each_failed_check():
    results = run_evaluations(DATA)
    assert all("checks" in result for result in results)
    assert all("expected_count" in result and "actual_count" in result for result in results)



def test_llm_planner_uses_allowlisted_plan_and_marks_mode():
    class FakePlanner:
        def plan(self, question, max_steps):
            return ["low_disk", "compliance_failures", "low_disk", "not_a_tool"]

    # Invalid model tool names force deterministic fallback rather than execution.
    agent = FleetAgent(load_snapshots(DATA), planner=FakePlanner())
    state = agent.invoke("Which devices have low disk space?", "acme-001")
    assert state.planner_mode == "deterministic_fallback"
    assert state.planner_error
    assert state.plan == ["low_disk"]
    assert all(item["company_id"] == "acme-001" for item in state.observations)


def test_llm_planner_accepts_valid_bounded_plan():
    class FakePlanner:
        def plan(self, question, max_steps):
            return ["compliance_failures", "low_disk", "ram_trends"]

    state = FleetAgent(load_snapshots(DATA), max_steps=2, planner=FakePlanner()).invoke(
        "Check compliance and disk", "acme-001"
    )
    assert state.planner_mode == "llm"
    assert state.plan == ["compliance_failures", "low_disk"]
