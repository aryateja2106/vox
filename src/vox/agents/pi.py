"""Pi coding agent wrapper.

Pi is a minimal terminal coding harness by Mario Zechner (@badlogic).
https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent

Install:  npm install -g @mariozechner/pi-coding-agent
"""

from __future__ import annotations

from vox.agents.base import AgentResult, BaseAgent


class PiAgent(BaseAgent):
    name = "pi"
    binary = "pi"
    description = "Pi coding agent — minimal, extensible terminal coding harness"

    @classmethod
    def run(cls, task: str, **kwargs: object) -> AgentResult:
        cmd = [cls.binary, "--print", task]
        return cls._exec(cmd)
