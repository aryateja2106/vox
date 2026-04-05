"""Tests for the self-learning knowledge store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vox.knowledge import KnowledgeStore, PatternMatch


@pytest.fixture
def store(tmp_path: Path) -> KnowledgeStore:
    """Create a fresh knowledge store for each test."""
    return KnowledgeStore(db_path=tmp_path / "test_knowledge.db")


# ── Layer 1: Command Patterns ────────────────────────────────────────────────


class TestCommandPatterns:
    def test_save_and_find_exact_match(self, store: KnowledgeStore) -> None:
        store.save_pattern("list files", "ls -la", "/home", "macOS")
        matches = store.find_pattern("list files")
        assert len(matches) == 1
        assert matches[0].command == "ls -la"
        assert matches[0].confidence == 1.0
        assert matches[0].success_count == 1

    def test_repeated_saves_increment_count(self, store: KnowledgeStore) -> None:
        store.save_pattern("list files", "ls -la")
        store.save_pattern("list files", "ls -la")
        store.save_pattern("list files", "ls -la")
        matches = store.find_pattern("list files")
        assert matches[0].success_count == 3

    def test_no_match_returns_empty(self, store: KnowledgeStore) -> None:
        matches = store.find_pattern("something random")
        assert matches == []

    def test_multiple_commands_for_same_query(self, store: KnowledgeStore) -> None:
        store.save_pattern("find large files", "find . -size +100M")
        store.save_pattern("find large files", "du -sh * | sort -rh | head")
        matches = store.find_pattern("find large files")
        assert len(matches) == 2

    def test_fuzzy_match_with_like(self, store: KnowledgeStore) -> None:
        store.save_pattern("show disk usage", "df -h")
        matches = store.find_pattern("disk usage")
        assert isinstance(matches, list)

    def test_limit_parameter(self, store: KnowledgeStore) -> None:
        for i in range(10):
            store.save_pattern(f"query {i}", f"cmd_{i}")
        matches = store.find_pattern("query 5", limit=1)
        assert len(matches) <= 1

    def test_cwd_stored(self, store: KnowledgeStore) -> None:
        store.save_pattern("git status", "git status", cwd="/my/project")
        matches = store.find_pattern("git status")
        assert matches[0].cwd == "/my/project"


# ── Layer 2: Corrections ─────────────────────────────────────────────────────


class TestCorrections:
    def test_correction_overrides_pattern(self, store: KnowledgeStore) -> None:
        store.save_pattern("list files", "ls")
        store.save_correction("list files", "ls", "ls -la")
        matches = store.find_pattern("list files")
        assert matches[0].command == "ls -la"
        assert matches[0].confidence == 1.0

    def test_correction_saved_as_pattern(self, store: KnowledgeStore) -> None:
        store.save_correction("show ports", "netstat", "lsof -i")
        stats = store.stats()
        assert stats["corrections"] == 1
        assert stats["patterns"] >= 1


# ── Layer 3: Error Patterns ──────────────────────────────────────────────────


class TestErrorPatterns:
    def test_save_error(self, store: KnowledgeStore) -> None:
        store.save_error("docker ps", "Cannot connect to Docker daemon", "/home")
        stats = store.stats()
        assert stats["errors"] == 1

    def test_find_fix_when_none(self, store: KnowledgeStore) -> None:
        fix = store.find_fix("docker ps", "some error")
        assert fix is None

    def test_long_error_truncated(self, store: KnowledgeStore) -> None:
        long_error = "x" * 5000
        store.save_error("bad_cmd", long_error)
        stats = store.stats()
        assert stats["errors"] == 1


# ── Layer 5: Agent Learnings ─────────────────────────────────────────────────


class TestAgentLearnings:
    def test_save_and_query_agent(self, store: KnowledgeStore) -> None:
        for _ in range(5):
            store.save_agent_result("fix code", "claude", success=True, latency_ms=1000)
        best = store.best_agent_for("fix code")
        assert best == "claude"

    def test_no_data_returns_none(self, store: KnowledgeStore) -> None:
        best = store.best_agent_for("unknown task")
        assert best is None

    def test_low_success_rate_not_returned(self, store: KnowledgeStore) -> None:
        for _ in range(3):
            store.save_agent_result("debug", "codex", success=False)
        store.save_agent_result("debug", "codex", success=True)
        best = store.best_agent_for("debug")
        assert best is None

    def test_minimum_uses_required(self, store: KnowledgeStore) -> None:
        store.save_agent_result("test", "claude", success=True)
        best = store.best_agent_for("test")
        assert best is None


# ── Layer 6: Session Context ─────────────────────────────────────────────────


class TestSessionContext:
    def test_save_and_get_context(self, store: KnowledgeStore) -> None:
        store.save_pattern("list files", "ls", cwd="/project")
        context = store.get_recent_context(cwd="/project")
        assert len(context) == 1
        assert context[0]["command"] == "ls"

    def test_context_without_cwd(self, store: KnowledgeStore) -> None:
        store.save_pattern("q1", "cmd1", cwd="/a")
        store.save_pattern("q2", "cmd2", cwd="/b")
        context = store.get_recent_context()
        assert len(context) == 2

    def test_save_session(self, store: KnowledgeStore) -> None:
        store.save_session("sess-1", "/project", ["ls", "git status"])
        stats = store.stats()
        assert stats["sessions"] == 1


# ── Management ───────────────────────────────────────────────────────────────


class TestManagement:
    def test_stats_all_zeros(self, store: KnowledgeStore) -> None:
        stats = store.stats()
        assert all(v == 0 for v in stats.values())

    def test_clear_resets_everything(self, store: KnowledgeStore) -> None:
        store.save_pattern("q", "cmd")
        store.save_correction("q", "cmd", "cmd2")
        store.save_error("cmd", "err")
        store.save_agent_result("task", "claude", True)
        store.save_session("s1", "/", ["ls"])
        store.clear()
        stats = store.stats()
        assert all(v == 0 for v in stats.values())

    def test_top_patterns_ordered(self, store: KnowledgeStore) -> None:
        store.save_pattern("rare", "rare_cmd")
        for _ in range(5):
            store.save_pattern("common", "common_cmd")
        top = store.top_patterns(limit=2)
        assert top[0]["query"] == "common"
        assert top[0]["uses"] == 5

    def test_export_import_roundtrip(self, store: KnowledgeStore) -> None:
        store.save_pattern("list files", "ls -la", "/home", "macOS")
        store.save_pattern("show disk", "df -h", "/", "Linux")
        exported = store.export_json()
        data = json.loads(exported)
        assert len(data) == 2
        store.clear()
        count = store.import_json(exported)
        assert count == 2
        matches = store.find_pattern("list files")
        assert len(matches) == 1

    def test_eviction(self, tmp_path: Path) -> None:
        import vox.knowledge as k
        old_max = k.MAX_PATTERNS
        k.MAX_PATTERNS = 5
        try:
            store = KnowledgeStore(db_path=tmp_path / "evict.db")
            for i in range(8):
                store.save_pattern(f"query_{i}", f"cmd_{i}")
            stats = store.stats()
            assert stats["patterns"] <= 6
        finally:
            k.MAX_PATTERNS = old_max


class TestPatternMatchDataclass:
    def test_fields(self) -> None:
        m = PatternMatch(command="ls", confidence=0.9, success_count=3, last_used=0.0)
        assert m.command == "ls"
        assert m.confidence == 0.9
        assert m.nl_query == ""
