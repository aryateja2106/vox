"""Tests for the agent system."""

from unittest.mock import patch

from vox.agents.base import AgentResult
from vox.agents.claude import ClaudeAgent
from vox.agents.codex import CodexAgent
from vox.agents.gemini import GeminiAgent
from vox.agents.router import ALL_AGENTS, discover_agents
from vox.config import VoxConfig


def test_all_agents_registered():
    names = {a.name for a in ALL_AGENTS}
    assert "claude" in names
    assert "codex" in names
    assert "gemini" in names
    assert "amp" in names
    assert "droid" in names


def test_agent_result_dataclass():
    r = AgentResult(agent="test", output="hello", exit_code=0)
    assert r.agent == "test"
    assert r.output == "hello"
    assert r.error is None


@patch("shutil.which")
def test_discover_agents_none(mock_which):
    mock_which.return_value = None
    assert discover_agents() == {}


@patch("shutil.which")
def test_discover_agents_finds_claude(mock_which):
    def side_effect(binary):
        if binary == "claude":
            return "/usr/local/bin/claude"
        return None

    mock_which.side_effect = side_effect
    agents = discover_agents()
    assert "claude" in agents
    assert agents["claude"] == "/usr/local/bin/claude"


@patch("vox.agents.base.BaseAgent._exec")
def test_claude_agent_run(mock_exec):
    mock_exec.return_value = AgentResult(agent="claude", output="done", exit_code=0)
    result = ClaudeAgent.run("fix the tests")
    assert result.agent == "claude"
    assert result.output == "done"
    cmd = mock_exec.call_args[0][0]
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "fix the tests" in cmd


@patch("vox.agents.base.BaseAgent._exec")
def test_codex_agent_run(mock_exec):
    mock_exec.return_value = AgentResult(agent="codex", output="fixed", exit_code=0)
    CodexAgent.run("fix tests")
    cmd = mock_exec.call_args[0][0]
    assert cmd[0] == "codex"
    assert "exec" in cmd


@patch("vox.agents.base.BaseAgent._exec")
def test_gemini_agent_run(mock_exec):
    mock_exec.return_value = AgentResult(agent="gemini", output="summary", exit_code=0)
    GeminiAgent.run("summarize the repo")
    cmd = mock_exec.call_args[0][0]
    assert cmd[0] == "gemini"
    assert "-p" in cmd


def test_agent_descriptions_not_empty():
    for agent_cls in ALL_AGENTS:
        assert agent_cls.description, f"{agent_cls.name} has no description"
        assert agent_cls.binary, f"{agent_cls.name} has no binary"


@patch("vox.agents.router.discover_agents")
def test_route_and_run_no_agents(mock_discover):
    from vox.agents.router import route_and_run

    mock_discover.return_value = {}
    cfg = VoxConfig()
    result = route_and_run("test task", cfg)
    assert "No AI agents" in result
