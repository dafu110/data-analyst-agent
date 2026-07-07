from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import request


class LLMPlannerError(RuntimeError):
    """Raised when an external planner cannot produce a valid JSON plan."""


@dataclass(frozen=True)
class OpenAIPlannerClient:
    model: str
    api_key: str

    def create_plan_json(self, user_goal: str, contract: dict[str, object]) -> dict[str, object]:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a data analysis planner. Return only JSON matching the supplied contract. "
                        "Do not include markdown. Do not request unsafe tools."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"user_goal": user_goal, "contract": contract}, ensure_ascii=False),
                },
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(http_request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = extract_response_text(data)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMPlannerError("Planner response was not valid JSON.") from exc


def build_planner_client_from_env() -> OpenAIPlannerClient | None:
    provider = os.getenv("DATA_ANALYST_AGENT_LLM_PROVIDER", "rules").lower()
    if provider != "openai":
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMPlannerError("OPENAI_API_KEY is required when DATA_ANALYST_AGENT_LLM_PROVIDER=openai.")
    model = os.getenv("DATA_ANALYST_AGENT_LLM_MODEL", "gpt-4.1-mini")
    return OpenAIPlannerClient(model=model, api_key=api_key)


def extract_response_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks: list[str] = []
    for output in data.get("output", []):
        for item in output.get("content", []):
            if item.get("type") in {"output_text", "text"} and isinstance(item.get("text"), str):
                chunks.append(item["text"])
    if not chunks:
        raise LLMPlannerError("Planner response did not include text content.")
    return "".join(chunks)
