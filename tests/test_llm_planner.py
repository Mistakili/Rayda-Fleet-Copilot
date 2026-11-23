from types import SimpleNamespace

from fleet_copilot.llm_planner import OpenAIPlanner


class FakeCompletions:
    def create(self, **kwargs):
        assert kwargs["response_format"] == {"type": "json_object"}
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"tools":["low_disk"]}'))]
        )


class FakeClient:
    chat = SimpleNamespace(completions=FakeCompletions())


def test_openai_planner_returns_structured_tool_plan():
    planner = OpenAIPlanner(model="test-model", client=FakeClient())
    assert planner.plan("Which devices have low disk space?", 4) == ["low_disk"]
