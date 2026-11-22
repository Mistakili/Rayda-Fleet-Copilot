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

def test_regression_evaluations_pass():
    assert all(x["passed"] for x in run_evaluations(DATA))
