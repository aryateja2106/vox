"""Tests for agent wrapper robustness — dataclass, _exec error handling, command construction."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from vox.agents.amp import AmpAgent
from vox.agents.base import AgentResult, BaseAgent
from vox.agents.claude import ClaudeAgent
from vox.agents.codex import CodexAgent
from vox.agents.droid import DroidAgent
from vox.agents.gemini import GeminiAgent
from vox.agents.router import ALL_AGENTS

# ---------------------------------------------------------------------------
# VAL-WRAP-001: AgentResult dataclass stores all fields with defaults
# ---------------------------------------------------------------------------


class TestAgentResultDataclass:
    def test_stores_all_explicit_fields(self):
        r = AgentResult(agent="test", output="hello", exit_code=1, error="fail")
        assert r.agent == "test"
        assert r.output == "hello"
        assert r.exit_code == 1
        assert r.error == "fail"

    def test_exit_code_defaults_to_zero(self):
        r = AgentResult(agent="a", output="b")
        assert r.exit_code == 0

    def test_error_defaults_to_none(self):
        r = AgentResult(agent="a", output="b")
        assert r.error is None

    def test_defaults_together(self):
        r = AgentResult(agent="x", output="y")
        assert r.exit_code == 0
        assert r.error is None


# ---------------------------------------------------------------------------
# VAL-WRAP-002: BaseAgent._exec handles timeout (exit_code=124)
# ---------------------------------------------------------------------------


class TestExecTimeoutHandling:
    @patch("vox.agents.base.subprocess.run")
    def test_timeout_returns_exit_code_124(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["test"], timeout=300)
        result = BaseAgent._exec(["test", "arg"])
        assert result.exit_code == 124

    @patch("vox.agents.base.subprocess.run")
    def test_timeout_returns_timed_out_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["test"], timeout=300)
        result = BaseAgent._exec(["test", "arg"])
        assert "timed out" in result.error.lower()

    @patch("vox.agents.base.subprocess.run")
    def test_timeout_returns_empty_output(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["test"], timeout=300)
        result = BaseAgent._exec(["test", "arg"])
        assert result.output == ""


# ---------------------------------------------------------------------------
# VAL-WRAP-003: BaseAgent._exec handles FileNotFoundError (exit_code=127)
# ---------------------------------------------------------------------------


class TestExecFileNotFoundHandling:
    @patch("vox.agents.base.subprocess.run")
    def test_file_not_found_returns_exit_code_127(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = BaseAgent._exec(["nonexistent", "arg"])
        assert result.exit_code == 127

    @patch("vox.agents.base.subprocess.run")
    def test_file_not_found_error_contains_binary_name(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = BaseAgent._exec(["nonexistent", "arg"])
        assert "not found" in result.error.lower()

    @patch("vox.agents.base.subprocess.run")
    def test_file_not_found_returns_empty_output(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = BaseAgent._exec(["nonexistent", "arg"])
        assert result.output == ""


# ---------------------------------------------------------------------------
# VAL-WRAP-006: Non-zero exit code captures stderr
# ---------------------------------------------------------------------------


class TestExecNonZeroExitWithStderr:
    @patch("vox.agents.base.subprocess.run")
    def test_nonzero_exit_captures_returncode(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="partial output",
            stderr="something went wrong",
            returncode=2,
        )
        result = BaseAgent._exec(["cmd"])
        assert result.exit_code == 2

    @patch("vox.agents.base.subprocess.run")
    def test_nonzero_exit_captures_stderr(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="partial output",
            stderr="something went wrong",
            returncode=2,
        )
        result = BaseAgent._exec(["cmd"])
        assert result.error == "something went wrong"

    @patch("vox.agents.base.subprocess.run")
    def test_nonzero_exit_captures_stdout(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="partial output",
            stderr="something went wrong",
            returncode=2,
        )
        result = BaseAgent._exec(["cmd"])
        assert result.output == "partial output"

    @patch("vox.agents.base.subprocess.run")
    def test_zero_exit_has_no_error(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="all good",
            stderr="",
            returncode=0,
        )
        result = BaseAgent._exec(["cmd"])
        assert result.exit_code == 0
        assert result.error is None


# ---------------------------------------------------------------------------
# VAL-WRAP-004: Each wrapper builds correct command list
# ---------------------------------------------------------------------------


class TestClaudeCommandConstruction:
    @patch("vox.agents.base.BaseAgent._exec")
    def test_claude_includes_binary(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="claude", output="ok")
        ClaudeAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert cmd[0] == "claude"

    @patch("vox.agents.base.BaseAgent._exec")
    def test_claude_includes_dash_p_and_task(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="claude", output="ok")
        ClaudeAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert "-p" in cmd
        assert "do stuff" in cmd

    @patch("vox.agents.base.BaseAgent._exec")
    def test_claude_includes_allowed_tools(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="claude", output="ok")
        ClaudeAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert "--allowedTools" in cmd

    @patch("vox.agents.base.BaseAgent._exec")
    def test_claude_includes_output_format_text(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="claude", output="ok")
        ClaudeAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert "--output-format" in cmd
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "text"


class TestCodexCommandConstruction:
    @patch("vox.agents.base.BaseAgent._exec")
    def test_codex_includes_binary(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="codex", output="ok")
        CodexAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert cmd[0] == "codex"

    @patch("vox.agents.base.BaseAgent._exec")
    def test_codex_uses_exec_subcommand(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="codex", output="ok")
        CodexAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert "exec" in cmd

    @patch("vox.agents.base.BaseAgent._exec")
    def test_codex_includes_task(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="codex", output="ok")
        CodexAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert "do stuff" in cmd


class TestGeminiCommandConstruction:
    @patch("vox.agents.base.BaseAgent._exec")
    def test_gemini_includes_binary_and_dash_p(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="gemini", output="ok")
        GeminiAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert cmd[0] == "gemini"
        assert "-p" in cmd
        assert "do stuff" in cmd


class TestAmpCommandConstruction:
    @patch("vox.agents.base.BaseAgent._exec")
    def test_amp_includes_binary_and_dash_p(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="amp", output="ok")
        AmpAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert cmd[0] == "amp"
        assert "-p" in cmd
        assert "do stuff" in cmd


class TestDroidCommandConstruction:
    @patch("vox.agents.base.BaseAgent._exec")
    def test_droid_includes_binary_and_dash_p(self, mock_exec):
        mock_exec.return_value = AgentResult(agent="droid", output="ok")
        DroidAgent.run("do stuff")
        cmd = mock_exec.call_args[0][0]
        assert cmd[0] == "droid"
        assert "-p" in cmd
        assert "do stuff" in cmd


# ---------------------------------------------------------------------------
# VAL-WRAP-005: All agents in ALL_AGENTS have non-empty name, binary, description
# ---------------------------------------------------------------------------


class TestAllAgentsAttributes:
    def test_all_agents_have_non_empty_name(self):
        for agent_cls in ALL_AGENTS:
            assert agent_cls.name, f"{agent_cls} has empty name"

    def test_all_agents_have_non_empty_binary(self):
        for agent_cls in ALL_AGENTS:
            assert agent_cls.binary, f"{agent_cls} has empty binary"

    def test_all_agents_have_non_empty_description(self):
        for agent_cls in ALL_AGENTS:
            assert agent_cls.description, f"{agent_cls} has empty description"

    def test_all_agents_count_at_least_five(self):
        assert len(ALL_AGENTS) >= 5


# ---------------------------------------------------------------------------
# VAL-CROSS-001: Integration — CLI agent subcommand flows through router
# ---------------------------------------------------------------------------


class TestCLIAgentIntegrationFlow:
    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.base.BaseAgent._exec")
    def test_refactor_task_flows_through_heuristic_to_wrapper(
        self, mock_exec, mock_discover
    ):
        """vox agent 'refactor auth' → heuristic picks claude → wrapper executes."""
        mock_discover.return_value = {"claude": "/usr/bin/claude", "gemini": "/usr/bin/gemini"}
        mock_exec.return_value = AgentResult(agent="claude", output="refactored!", exit_code=0)

        from vox.agents.router import route_and_run
        from vox.config import VoxConfig

        cfg = VoxConfig()
        result = route_and_run("refactor auth", cfg)
        assert "claude" in result
        assert "refactored!" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.base.BaseAgent._exec")
    def test_research_task_flows_through_heuristic_to_gemini(
        self, mock_exec, mock_discover
    ):
        """vox agent 'research best practices' → heuristic picks gemini → wrapper executes."""
        mock_discover.return_value = {"claude": "/usr/bin/claude", "gemini": "/usr/bin/gemini"}
        mock_exec.return_value = AgentResult(agent="gemini", output="found info", exit_code=0)

        from vox.agents.router import route_and_run
        from vox.config import VoxConfig

        cfg = VoxConfig()
        result = route_and_run("research best practices", cfg)
        assert "gemini" in result
        assert "found info" in result
