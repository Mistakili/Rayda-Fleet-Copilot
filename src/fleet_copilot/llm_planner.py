"""Optional OpenAI-backed planner. Model output is restricted to an allowlisted tool plan."""
from __future__ import annotations

import json
import os
from typing import Any

from .agent import ALLOWED_TOOLS


class OpenAIPlanner:
    def __init__(self, model: str | None = None, client: Any | None = None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.client = client
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def plan(self, question: str, max_steps: int) -> list[str]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a fleet telemetry query planner. Select tools only; do not answer "
                        "the user, infer facts, choose a tenant, or propose actions. Return JSON "
                        'with one key "tools", an array ordered by relevance. Allowed tools: '
                        + ", ".join(sorted(ALLOWED_TOOLS))
                        + f". Select between 1 and {max_steps} tools. Use only tools needed "
                        "to answer the question. For broad historical trend reviews, consider "
                        "battery_trends, ram_trends, storage_trends and compliance_drift. "
                        "For disk capacity questions use low_disk. For compliance questions use "
                        "compliance_failures. For memory pressure use ram_trends."
                    ),
                },
                {"role": "user", "content": question},
            ],
        )
        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("The model returned an empty plan")
        parsed = json.loads(raw)
        tools = parsed.get("tools")
        if not isinstance(tools, list):
            raise ValueError("The model response must contain a tools array")
        return tools
