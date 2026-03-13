"""Agent router — discover installed agents and auto-route tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vox.agents.amp import AmpAgent
from vox.agents.claude import ClaudeAgent
from vox.agents.codex import CodexAgent
from vox.agents.droid import DroidAgent
from vox.agents.gemini import GeminiAgent
from vox.agents.pi import PiAgent

if TYPE_CHECKING:
    from vox.agents.base import AgentResult, BaseAgent
    from vox.config import VoxConfig

ALL_AGENTS: list[type[BaseAgent]] = [
    ClaudeAgent,
    CodexAgent,
    GeminiAgent,
    AmpAgent,
    DroidAgent,
    PiAgent,
]

ROUTE_SYSTEM_PROMPT = """\
You are an agent router. Given a task description, pick the single best agent \
to handle it from the available list. Reply with ONLY the agent name, nothing else.

Available agents:
{agents}

Rules:
- For code editing, refactoring, debugging → prefer claude or codex
- For research, summarization, questions → prefer gemini
- For complex multi-step engineering → prefer droid
- For codebase search and understanding → prefer amp
- For minimal/lightweight terminal tasks → prefer pi
- If unsure, use the preferred agent
"""


def discover_agents() -> dict[str, str]:
    """Scan PATH for known agent binaries. Returns {name: path}."""
    found = {}
    for agent_cls in ALL_AGENTS:
        path = agent_cls.is_available()
        if path:
            found[agent_cls.name] = path
    return found


def _pick_agent(task: str, available: dict[str, str], cfg: VoxConfig) -> type[BaseAgent]:
    """Use the local LLM to pick the best agent for a task."""
    from vox.engine import query_llm

    agent_map = {a.name: a for a in ALL_AGENTS if a.name in available}

    if len(agent_map) == 1:
        return next(iter(agent_map.values()))

    agents_desc = "\n".join(
        f"- {a.name}: {a.description}" for a in ALL_AGENTS if a.name in available
    )

    system = ROUTE_SYSTEM_PROMPT.format(agents=agents_desc)
    response = query_llm(f"Task: {task}", cfg=cfg, system=system)

    if response:
        choice = response.strip().lower().split()[0] if response.strip() else ""
        choice = choice.strip(".-*`'\"")
        if choice in agent_map:
            return agent_map[choice]

    preferred = cfg.agents.preferred
    if preferred in agent_map:
        return agent_map[preferred]

    return next(iter(agent_map.values()))


def route_and_run(
    task: str,
    cfg: VoxConfig,
    force_agent: str | None = None,
) -> str:
    """Route a task to the best agent and run it. Returns formatted output."""
    import os

    force_agent = force_agent or os.environ.get("VOX_PREFERRED_AGENT")

    available = discover_agents()
    if not available:
        return "[yellow]No AI agents found in PATH. Install claude, codex, gemini, amp, or droid.[/yellow]"

    agent_map = {a.name: a for a in ALL_AGENTS if a.name in available}

    if force_agent and force_agent in agent_map:
        agent_cls = agent_map[force_agent]
    elif cfg.agents.auto_route and len(agent_map) > 1:
        agent_cls = _pick_agent(task, available, cfg)
    else:
        preferred = cfg.agents.preferred
        agent_cls = agent_map.get(preferred, next(iter(agent_map.values())))

    result: AgentResult = agent_cls.run(task)

    header = f"[bold cyan]{result.agent}[/bold cyan]"
    if result.exit_code != 0:
        error_msg = result.error or "unknown error"
        return f"{header} [red]failed (exit {result.exit_code})[/red]\n{error_msg}"

    if result.output:
        return f"{header}\n{result.output}"
    return f"{header} [dim]completed (no output)[/dim]"
