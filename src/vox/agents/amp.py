"""Amp (Sourcegraph) headless agent wrapper."""

from __future__ import annotations

from vox.agents.base import AgentResult, BaseAgent


class AmpAgent(BaseAgent):
    name = "amp"
    binary = "amp"
    description = "Sourcegraph Amp — best for codebase understanding, search, navigation"

    @classmethod
    def run(cls, task: str, **kwargs) -> AgentResult:
        cmd = [cls.binary, "-p", task]
        return cls._exec(cmd)
