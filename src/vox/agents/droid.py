"""Factory Droid headless agent wrapper."""

from __future__ import annotations

from vox.agents.base import AgentResult, BaseAgent


class DroidAgent(BaseAgent):
    name = "droid"
    binary = "droid"
    description = "Factory Droid — best for complex multi-step engineering tasks"

    @classmethod
    def run(cls, task: str, **kwargs: object) -> AgentResult:
        cmd = [cls.binary, "-p", task]
        return cls._exec(cmd)
