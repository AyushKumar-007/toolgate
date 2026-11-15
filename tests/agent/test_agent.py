from pathlib import Path

import pytest

from toolgate.agent import MockAgent, OllamaAgent
from toolgate.agent.ollama import tool_calls_from_message
from toolgate.domain.models import Case
from toolgate.domain.protocols import Agent
from toolgate.domain.vocab import ToolName

CASES = Path(__file__).resolve().parents[2] / "data" / "cases" / "legitimate"


class FakePoster:
    def __init__(self, message: dict) -> None:
        self.message = message
        self.calls: list[tuple[str, dict]] = []

    def post_json(self, url: str, payload: dict) -> dict:
        self.calls.append((url, payload))
        return {"message": self.message}


def test_mock_agent_replays_case() -> None:
    case = Case.model_validate_json((CASES / "case_legit_read.json").read_text(encoding="utf-8"))
    agent = MockAgent()
    assert isinstance(agent, Agent)
    assert agent.propose(case) == case.proposals


def test_tool_calls_from_message() -> None:
    message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "c1",
                "function": {
                    "name": "read_record",
                    "arguments": {"record_id": "rec_a1"},
                },
            }
        ],
    }
    calls = tool_calls_from_message(message)
    assert len(calls) == 1
    assert calls[0].name is ToolName.read_record
    assert calls[0].call_id == "c1"


def test_ollama_agent_uses_poster() -> None:
    case = Case.model_validate_json((CASES / "case_legit_read.json").read_text(encoding="utf-8"))
    poster = FakePoster(
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "list_records",
                        "arguments": {"tenant_id": "ten_a"},
                    },
                }
            ],
        }
    )
    agent = OllamaAgent(poster=poster, model="test-model")
    assert isinstance(agent, Agent)
    calls = agent.propose(case)
    assert calls[0].call_id == "call_1"
    assert poster.calls[0][0].endswith("/api/chat")
    assert "tools" in poster.calls[0][1]


def test_ollama_agent_unreachable() -> None:
    class Boom:
        def post_json(self, url: str, payload: dict) -> dict:
            raise ConnectionError("down")

    case = Case.model_validate_json((CASES / "case_legit_read.json").read_text(encoding="utf-8"))
    with pytest.raises(ConnectionError):
        OllamaAgent(poster=Boom()).propose(case)
