"""OpenAI Codex CLI headless agent wrapper."""

from __future__ import annotations

from vox.agents.base import AgentResult, BaseAgent


class CodexAgent(BaseAgent):
    name = "codex"
    binary = "codex"
    description = "OpenAI Codex — best for code generation, test fixes, CI tasks"

    @classmethod
    def run(cls, task: str, **kwargs) -> AgentResult:
        cmd = [cls.binary, "exec", task]
        if kwargs.get("full_auto"):
            cmd.append("--full-auto")
        return cls._exec(cmd)
