"""Tests for the heuristic keyword router."""

from __future__ import annotations

from unittest.mock import patch

from vox.agents.base import AgentResult
from vox.agents.router import (
    ALL_AGENTS,
    discover_agents,
    route_and_run,
)
from vox.config import VoxConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(preferred: str = "claude", auto_route: bool = True) -> VoxConfig:
    """Return a VoxConfig with agents settings overridden."""
    cfg = VoxConfig()
    cfg.agents.preferred = preferred
    cfg.agents.auto_route = auto_route
    return cfg


def _available_coding_and_research() -> dict[str, str]:
    """Return agents dict with both coding (claude, codex) and research (gemini)."""
    return {
        "claude": "/usr/local/bin/claude",
        "codex": "/usr/local/bin/codex",
        "gemini": "/usr/local/bin/gemini",
    }


def _available_all() -> dict[str, str]:
    """All agents available."""
    return {
        "claude": "/usr/local/bin/claude",
        "codex": "/usr/local/bin/codex",
        "gemini": "/usr/local/bin/gemini",
        "amp": "/usr/local/bin/amp",
        "droid": "/usr/local/bin/droid",
    }


# ---------------------------------------------------------------------------
# VAL-RTR-001: Coding keywords route to coding agent WITHOUT calling LLM
# ---------------------------------------------------------------------------

class TestHeuristicCodingKeywords:
    """Coding keywords (refactor, code, fix, debug, implement) route to claude/codex."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_refactor_routes_to_coding_agent(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("refactor the auth module", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_code_routes_to_coding_agent(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("code a new feature", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_fix_routes_to_coding_agent(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("fix the broken tests", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_debug_routes_to_coding_agent(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("debug the memory leak", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_implement_routes_to_coding_agent(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("implement the login flow", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result


# ---------------------------------------------------------------------------
# VAL-RTR-002: Research keywords route to gemini WITHOUT calling LLM
# ---------------------------------------------------------------------------

class TestHeuristicResearchKeywords:
    """Research keywords (research, search, summarize) route to gemini."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_research_routes_to_gemini(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="summary", exit_code=0)):
            result = route_and_run("research best practices for auth", _cfg())
        mock_llm.assert_not_called()
        assert "gemini" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_search_routes_to_gemini(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="found it", exit_code=0)):
            result = route_and_run("search for documentation on httpx", _cfg())
        mock_llm.assert_not_called()
        assert "gemini" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_summarize_routes_to_gemini(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="summary", exit_code=0)):
            result = route_and_run("summarize the readme file", _cfg())
        mock_llm.assert_not_called()
        assert "gemini" in result


# ---------------------------------------------------------------------------
# VAL-RTR-003: Case-insensitive matching
# ---------------------------------------------------------------------------

class TestCaseInsensitiveMatching:
    """Keywords match regardless of case."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_uppercase_refactor_matches(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("REFACTOR the auth module", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_mixed_case_research_matches(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="data", exit_code=0)):
            result = route_and_run("Research the API design", _cfg())
        mock_llm.assert_not_called()
        assert "gemini" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_uppercase_fix_matches(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("FIX the broken build", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result


# ---------------------------------------------------------------------------
# VAL-RTR-014: Word boundary matching — prevents false positives
# ---------------------------------------------------------------------------

class TestWordBoundaryMatching:
    """Keyword 'fix' should NOT match 'prefix', 'code' should NOT match 'barcode'."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_fix_does_not_match_prefix(self, mock_llm, mock_discover):
        """'fix' in 'prefix' should NOT trigger coding heuristic."""
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = "claude"
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            route_and_run("update the prefix for the namespace", _cfg())
        # LLM should have been called because no keyword matched
        mock_llm.assert_called()

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_fix_does_not_match_suffix(self, mock_llm, mock_discover):
        """'fix' in 'suffix' should NOT trigger coding heuristic."""
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = "claude"
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            route_and_run("change the suffix of each file", _cfg())
        mock_llm.assert_called()

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_code_does_not_match_barcode(self, mock_llm, mock_discover):
        """'code' in 'barcode' should NOT trigger coding heuristic."""
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = "claude"
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            route_and_run("scan the barcode label", _cfg())
        mock_llm.assert_called()

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_search_does_not_match_researcher(self, mock_llm, mock_discover):
        """'search' in 'researcher' should NOT trigger research heuristic."""
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = "claude"
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            route_and_run("email the researcher about results", _cfg())
        mock_llm.assert_called()


# ---------------------------------------------------------------------------
# VAL-RTR-015: Conflicting keywords — coding takes priority
# ---------------------------------------------------------------------------

class TestConflictingKeywords:
    """When both coding and research keywords present, coding takes priority."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_coding_priority_over_research(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("research and fix the auth bug", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_implement_beats_summarize(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("summarize the codebase and implement new tests", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result


# ---------------------------------------------------------------------------
# VAL-RTR-004: No keyword match + multiple agents + auto_route → LLM fallback
# ---------------------------------------------------------------------------

class TestLLMFallback:
    """When heuristic doesn't match and multiple agents + auto_route → LLM called."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_no_keyword_triggers_llm_fallback(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = "claude"
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            route_and_run("help me with this project", _cfg())
        mock_llm.assert_called()

    # VAL-RTR-005: LLM returns valid agent name → selected
    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_llm_valid_response_selects_agent(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = "gemini"
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="done", exit_code=0)):
            result = route_and_run("help me with this project", _cfg())
        assert "gemini" in result

    # VAL-RTR-006: LLM returns garbage → preferred fallback
    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_llm_garbage_falls_back_to_preferred(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = "$$garbage!!"
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("help me with this project", _cfg(preferred="claude"))
        assert "claude" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_llm_none_falls_back_to_preferred(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        mock_llm.return_value = None
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("help me with this project", _cfg(preferred="claude"))
        assert "claude" in result


# ---------------------------------------------------------------------------
# VAL-RTR-007: No agents → graceful error
# ---------------------------------------------------------------------------

class TestNoAgents:
    """When no agents discovered, return user-friendly error."""

    @patch("vox.agents.router.discover_agents")
    def test_no_agents_returns_message(self, mock_discover):
        mock_discover.return_value = {}
        result = route_and_run("do something", _cfg())
        assert "No AI agents" in result
        # Mentions at least one installable agent
        assert any(name in result for name in ("claude", "codex", "gemini", "amp", "droid"))


# ---------------------------------------------------------------------------
# VAL-RTR-008: Single agent → used directly without LLM
# ---------------------------------------------------------------------------

class TestSingleAgent:
    """When only one agent, use it directly; LLM not called."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_single_agent_used_directly(self, mock_llm, mock_discover):
        mock_discover.return_value = {"gemini": "/usr/local/bin/gemini"}
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="result", exit_code=0)):
            result = route_and_run("do something random", _cfg())
        mock_llm.assert_not_called()
        assert "gemini" in result


# ---------------------------------------------------------------------------
# VAL-RTR-009: force_agent overrides all routing
# ---------------------------------------------------------------------------

class TestForceAgent:
    """force_agent parameter overrides heuristic and LLM routing."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_force_agent_overrides_heuristic(self, mock_llm, mock_discover):
        """Even with a coding keyword, force_agent=gemini should use gemini."""
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="done", exit_code=0)):
            result = route_and_run("fix the auth module", _cfg(), force_agent="gemini")
        mock_llm.assert_not_called()
        assert "gemini" in result

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_force_agent_via_env_var(self, mock_llm, mock_discover):
        """VOX_PREFERRED_AGENT env var acts as force_agent."""
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="done", exit_code=0)), patch.dict("os.environ", {"VOX_PREFERRED_AGENT": "gemini"}):


                result = route_and_run("fix bugs everywhere", _cfg())
        mock_llm.assert_not_called()
        assert "gemini" in result


# ---------------------------------------------------------------------------
# VAL-RTR-016: Force agent unavailable → falls through
# ---------------------------------------------------------------------------

class TestForceAgentUnavailable:
    """When forced agent isn't available, fall through to normal routing."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_force_agent_unavailable_falls_through(self, mock_llm, mock_discover):
        mock_discover.return_value = {"claude": "/usr/local/bin/claude"}
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("fix the tests", _cfg(), force_agent="nonexistent")
        # Should route normally (heuristic: "fix" → claude)
        assert "claude" in result


# ---------------------------------------------------------------------------
# VAL-RTR-010: auto_route=False → preferred agent
# ---------------------------------------------------------------------------

class TestAutoRouteDisabled:
    """With auto_route=False, routes to preferred without heuristic or LLM."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_auto_route_false_uses_preferred(self, mock_llm, mock_discover):
        mock_discover.return_value = _available_coding_and_research()
        with patch.object(ALL_AGENTS[2], "run", return_value=AgentResult(agent="gemini", output="done", exit_code=0)):
            result = route_and_run("fix the tests", _cfg(preferred="gemini", auto_route=False))
        mock_llm.assert_not_called()
        assert "gemini" in result


# ---------------------------------------------------------------------------
# VAL-RTR-011: Heuristic priority is absolute over LLM
# ---------------------------------------------------------------------------

class TestHeuristicPriorityOverLLM:
    """When heuristic matches, LLM is NEVER called regardless of settings."""

    @patch("vox.agents.router.discover_agents")
    @patch("vox.agents.router.query_llm")
    def test_heuristic_match_skips_llm_with_multiple_agents(self, mock_llm, mock_discover):
        """Even with auto_route=True and 5 agents, heuristic match skips LLM."""
        mock_discover.return_value = _available_all()
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="done", exit_code=0)):
            result = route_and_run("debug the memory leak", _cfg())
        mock_llm.assert_not_called()
        assert "claude" in result or "codex" in result


# ---------------------------------------------------------------------------
# VAL-RTR-012: Agent discovery scans PATH correctly
# ---------------------------------------------------------------------------

class TestAgentDiscovery:
    """discover_agents() returns {name: path} for available agents."""

    @patch("shutil.which")
    def test_discovers_selective_agents(self, mock_which):
        def side_effect(binary):
            if binary == "claude":
                return "/usr/local/bin/claude"
            if binary == "gemini":
                return "/opt/bin/gemini"
            return None

        mock_which.side_effect = side_effect
        agents = discover_agents()
        assert agents == {"claude": "/usr/local/bin/claude", "gemini": "/opt/bin/gemini"}

    @patch("shutil.which")
    def test_discovers_all_agents(self, mock_which):
        mock_which.return_value = "/usr/local/bin/agent"
        agents = discover_agents()
        assert len(agents) == len(ALL_AGENTS)
        for agent_cls in ALL_AGENTS:
            assert agent_cls.name in agents


# ---------------------------------------------------------------------------
# VAL-RTR-013: Output formatting for success/failure/empty
# ---------------------------------------------------------------------------

class TestOutputFormatting:
    """Output formatted correctly for success, failure, and empty cases."""

    @patch("vox.agents.router.discover_agents")
    def test_success_shows_agent_and_output(self, mock_discover):
        mock_discover.return_value = {"claude": "/usr/local/bin/claude"}
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="refactored 5 files", exit_code=0)):
            result = route_and_run("fix it", _cfg())
        assert "claude" in result
        assert "refactored 5 files" in result

    @patch("vox.agents.router.discover_agents")
    def test_failure_shows_error(self, mock_discover):
        mock_discover.return_value = {"claude": "/usr/local/bin/claude"}
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="", exit_code=1, error="command failed")):
            result = route_and_run("fix it", _cfg())
        assert "failed" in result
        assert "command failed" in result

    @patch("vox.agents.router.discover_agents")
    def test_empty_output_shows_completed(self, mock_discover):
        mock_discover.return_value = {"claude": "/usr/local/bin/claude"}
        with patch.object(ALL_AGENTS[0], "run", return_value=AgentResult(agent="claude", output="", exit_code=0)):
            result = route_and_run("fix it", _cfg())
        assert "completed" in result
        assert "no output" in result


# ---------------------------------------------------------------------------
# _heuristic_route function direct tests
# ---------------------------------------------------------------------------

class TestHeuristicRouteFunction:
    """Direct tests for the _heuristic_route() function."""

    def test_heuristic_route_exists(self):
        """_heuristic_route function should be importable from router."""
        from vox.agents.router import _heuristic_route
        assert callable(_heuristic_route)

    def test_heuristic_returns_none_for_no_match(self):
        from vox.agents.router import _heuristic_route
        agent_map = {a.name: a for a in ALL_AGENTS}
        result = _heuristic_route("help me with something", agent_map)
        assert result is None

    def test_heuristic_returns_coding_agent_for_fix(self):
        from vox.agents.router import _heuristic_route
        agent_map = {a.name: a for a in ALL_AGENTS}
        result = _heuristic_route("fix the broken test", agent_map)
        assert result is not None
        assert result.name in ("claude", "codex")

    def test_heuristic_returns_gemini_for_research(self):
        from vox.agents.router import _heuristic_route
        agent_map = {a.name: a for a in ALL_AGENTS}
        result = _heuristic_route("research the best approach", agent_map)
        assert result is not None
        assert result.name == "gemini"

    def test_heuristic_only_routes_if_agent_available(self):
        """If coding agents aren't available, coding keywords return None."""
        from vox.agents.router import _heuristic_route
        # Only gemini available
        agent_map = {"gemini": ALL_AGENTS[2]}
        result = _heuristic_route("fix the tests", agent_map)
        assert result is None
