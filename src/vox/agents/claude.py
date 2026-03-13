"""Claude Code headless agent wrapper."""

from __future__ import annotations

from vox.agents.base import AgentResult, BaseAgent


class ClaudeAgent(BaseAgent):
    name = "claude"
    binary = "claude"
    description = "Anthropic Claude Code — best for code refactoring, debugging, architecture"

    @classmethod
    def run(cls, task: str, **kwargs: object) -> AgentResult:
        allowed_tools = str(kwargs.get("allowed_tools", "Read,Edit,Bash"))
        cmd = [
            cls.binary,
            "-p",
            task,
            "--allowedTools",
            allowed_tools,
            "--output-format",
            "text",
        ]
        return cls._exec(cmd)
