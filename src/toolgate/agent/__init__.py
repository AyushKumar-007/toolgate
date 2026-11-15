"""Agents that propose tool calls. Mock agent is the measured path."""

from toolgate.agent.mock import MockAgent
from toolgate.agent.ollama import OllamaAgent

__all__ = ["MockAgent", "OllamaAgent"]
