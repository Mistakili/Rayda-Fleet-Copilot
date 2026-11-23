from pathlib import Path
from types import SimpleNamespace

import pytest

from fleet_copilot.data import load_snapshots
from fleet_copilot.llm_agent import OpenAIFleetAgent

DATA = Path(__file__).parents[1] / "data" / "device-telemetry-dataset.ndjson"


class FakeClient:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.calls = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=next(self.messages))])


def assistant_tool_call(name, arguments="{}", call_id="call_1"):
    function = SimpleNamespace(name=name, arguments=arguments)
    call = SimpleNamespace(id=call_id, function=function)
    message = SimpleNamespace(tool_calls=[call], content=None, model_dump=lambda **kwargs: {
        "role": "assistant",
        "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}],
    })
    return message


def assistant_final(content):
    return SimpleNamespace(tool_calls=None, content=content)


def test_openai_agent_uses_model_tool_choice_but_trusted_tenant_scope():
    client = FakeClient([
        assistant_tool_call("low_disk"),
        assistant_final("Two low-disk findings were returned for the authenticated tenant."),
    ])
    agent = OpenAIFleetAgent(load_snapshots(DATA), client=client)
    state = agent.invoke("Find devices with low storage", "acme-001")

    assert state.plan == ["low_disk"]
    assert state.observations[0]["company_id"] == "acme-001"
    assert state.observations[0]["count"] == 2
    assert state.answer.startswith("Two low-disk")
    assert client.calls[0]["temperature"] == 0


def test_openai_agent_rejects_model_supplied_tenant_arguments():
    client = FakeClient([
        assistant_tool_call("low_disk", '{"company_id":"globex-001"}'),
        assistant_final("The tool call was rejected."),
    ])
    state = OpenAIFleetAgent(load_snapshots(DATA), client=client).invoke("Show disk", "acme-001")
    assert state.observations == []
    assert state.plan == []


def test_openai_agent_rejects_unknown_tools_without_execution():
    client = FakeClient([
        assistant_tool_call("delete_device"),
        assistant_final("I cannot perform that operation."),
    ])
    state = OpenAIFleetAgent(load_snapshots(DATA), client=client).invoke("Delete a device", "acme-001")
    assert state.observations == []
    assert state.plan == []


def test_openai_agent_enforces_tool_call_bound():
    client = FakeClient([
        assistant_tool_call("low_disk", call_id="one"),
        assistant_tool_call("compliance_failures", call_id="two"),
        assistant_final("Investigation completed within the tool limit."),
    ])
    agent = OpenAIFleetAgent(load_snapshots(DATA), max_steps=1, client=client)
    state = agent.invoke("Investigate the fleet", "acme-001")
    assert len(state.observations) == 1
    assert len(state.steps) == 1
    assert client.calls[-1]["tool_choice"] == "none"


def test_openai_agent_requires_authenticated_tenant_and_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Authenticated company"):
        OpenAIFleetAgent([], client=FakeClient([])).invoke("disk", "")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIFleetAgent([], api_key="", client=None)
