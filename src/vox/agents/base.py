"""Base agent interface for headless CLI agent wrappers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class AgentResult:
    agent: str
    output: str
    exit_code: int = 0
    error: str | None = None


class BaseAgent:
    """Abstract base for CLI agent wrappers."""

    name: str = "base"
    binary: str = ""
    description: str = ""

    @classmethod
    def is_available(cls) -> str | None:
        """Return the binary path if available, None otherwise."""
        return shutil.which(cls.binary)

    @classmethod
    def run(cls, task: str, **kwargs) -> AgentResult:
        """Execute a task via this agent's headless mode."""
        raise NotImplementedError

    @classmethod
    def _exec(cls, cmd: list[str], timeout: int = 300) -> AgentResult:
        """Run a subprocess and capture output."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return AgentResult(
                agent=cls.name,
                output=result.stdout.strip(),
                exit_code=result.returncode,
                error=result.stderr.strip() if result.returncode != 0 else None,
            )
        except subprocess.TimeoutExpired:
            return AgentResult(
                agent=cls.name, output="", exit_code=124, error="Agent timed out"
            )
        except FileNotFoundError:
            return AgentResult(
                agent=cls.name, output="", exit_code=127, error=f"{cls.binary} not found"
            )
