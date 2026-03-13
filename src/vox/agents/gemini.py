"""Google Gemini CLI headless agent wrapper."""

from __future__ import annotations

from vox.agents.base import AgentResult, BaseAgent


class GeminiAgent(BaseAgent):
    name = "gemini"
    binary = "gemini"
    description = "Google Gemini — best for research, summarization, multi-language tasks"

    @classmethod
    def run(cls, task: str, **kwargs) -> AgentResult:
        cmd = [cls.binary, "-p", task]
        return cls._exec(cmd)
