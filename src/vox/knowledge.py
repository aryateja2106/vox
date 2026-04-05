"""Self-learning knowledge store — SQLite-backed memory for command patterns, corrections, and errors."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".config" / "vox" / "knowledge.db"
MAX_PATTERNS = 10_000


@dataclass
class PatternMatch:
    """A matched command pattern with confidence scoring."""

    command: str
    confidence: float
    success_count: int
    last_used: float
    nl_query: str = ""
    cwd: str = ""


class KnowledgeStore:
    """SQLite-backed self-learning store with 6 context layers.

    Layer 1: Command patterns — validated NL→shell mappings that worked
    Layer 2: User corrections — when the user rejects and provides the right command
    Layer 3: Error patterns — commands that failed and what fixed them
    Layer 5: Agent learnings — which agent works best for which task type
    Layer 6: Session context — current directory, recent commands
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = str(db_path or DEFAULT_DB_PATH)
        self._db_path_obj = db_path or DEFAULT_DB_PATH
        self._db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        self._has_fts5 = False
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            # Layer 1: Command patterns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS command_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nl_query TEXT NOT NULL,
                    shell_cmd TEXT NOT NULL,
                    cwd TEXT DEFAULT '',
                    os_name TEXT DEFAULT '',
                    success_count INTEGER DEFAULT 1,
                    last_used REAL NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(nl_query, shell_cmd)
                )
            """)

            # Layer 2: User corrections
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nl_query TEXT NOT NULL,
                    rejected_cmd TEXT NOT NULL,
                    correct_cmd TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)

            # Layer 3: Error patterns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shell_cmd TEXT NOT NULL,
                    error_output TEXT NOT NULL,
                    fix_cmd TEXT DEFAULT '',
                    cwd TEXT DEFAULT '',
                    timestamp REAL NOT NULL
                )
            """)

            # Layer 5: Agent learnings
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 1,
                    latency_ms INTEGER DEFAULT 0,
                    timestamp REAL NOT NULL
                )
            """)

            # Layer 6: Session context
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    cwd TEXT DEFAULT '',
                    recent_cmds TEXT DEFAULT '[]',
                    env_snapshot TEXT DEFAULT '{}',
                    timestamp REAL NOT NULL
                )
            """)

            # Try to create FTS5 index for fuzzy matching
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS patterns_fts
                    USING fts5(nl_query, content=command_patterns, content_rowid=id)
                """)
                self._has_fts5 = True
            except sqlite3.OperationalError:
                # FTS5 not available on this platform
                self._has_fts5 = False

            conn.commit()
        finally:
            conn.close()

    # ── Layer 1: Command Patterns ────────────────────────────────────────────

    def save_pattern(self, nl_query: str, shell_cmd: str, cwd: str = "", os_name: str = "") -> None:
        """Save a successful NL→shell command mapping."""
        now = time.time()
        conn = self._get_conn()
        try:
            # Try to update existing pattern
            cursor = conn.execute(
                """UPDATE command_patterns
                   SET success_count = success_count + 1, last_used = ?, cwd = ?, os_name = ?
                   WHERE nl_query = ? AND shell_cmd = ?""",
                (now, cwd, os_name, nl_query, shell_cmd),
            )
            if cursor.rowcount == 0:
                # Insert new pattern
                conn.execute(
                    """INSERT INTO command_patterns (nl_query, shell_cmd, cwd, os_name, last_used, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (nl_query, shell_cmd, cwd, os_name, now, now),
                )
                # Sync FTS index
                if self._has_fts5:
                    row = conn.execute(
                        "SELECT id FROM command_patterns WHERE nl_query = ? AND shell_cmd = ?",
                        (nl_query, shell_cmd),
                    ).fetchone()
                    if row:
                        conn.execute(
                            "INSERT INTO patterns_fts(rowid, nl_query) VALUES (?, ?)",
                            (row["id"], nl_query),
                        )
                self._evict_if_needed(conn)
            conn.commit()
        finally:
            conn.close()

    def find_pattern(self, nl_query: str, cwd: str | None = None, limit: int = 3) -> list[PatternMatch]:
        """Find matching patterns for a natural language query."""
        conn = self._get_conn()
        try:
            matches: list[PatternMatch] = []

            # First: check for correction overrides (Layer 2 takes priority)
            correction = conn.execute(
                "SELECT correct_cmd FROM corrections WHERE nl_query = ? ORDER BY timestamp DESC LIMIT 1",
                (nl_query,),
            ).fetchone()
            if correction:
                matches.append(
                    PatternMatch(
                        command=correction["correct_cmd"],
                        confidence=1.0,
                        success_count=999,
                        last_used=time.time(),
                        nl_query=nl_query,
                    )
                )
                return matches

            # Exact match (highest confidence)
            exact = conn.execute(
                """SELECT shell_cmd, success_count, last_used, cwd
                   FROM command_patterns WHERE nl_query = ?
                   ORDER BY success_count DESC, last_used DESC LIMIT ?""",
                (nl_query, limit),
            ).fetchall()
            for row in exact:
                matches.append(
                    PatternMatch(
                        command=row["shell_cmd"],
                        confidence=1.0,
                        success_count=row["success_count"],
                        last_used=row["last_used"],
                        nl_query=nl_query,
                        cwd=row["cwd"],
                    )
                )

            if matches:
                return matches

            # FTS5 fuzzy match (lower confidence, weighted by success_count)
            if self._has_fts5:
                fts_results = conn.execute(
                    """SELECT cp.shell_cmd, cp.success_count, cp.last_used, cp.nl_query, cp.cwd,
                              rank
                       FROM patterns_fts fts
                       JOIN command_patterns cp ON fts.rowid = cp.id
                       WHERE patterns_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (nl_query, limit),
                ).fetchall()
                for row in fts_results:
                    # Confidence based on FTS rank + success count
                    base_confidence = min(0.85, 0.5 + (row["success_count"] * 0.05))
                    matches.append(
                        PatternMatch(
                            command=row["shell_cmd"],
                            confidence=base_confidence,
                            success_count=row["success_count"],
                            last_used=row["last_used"],
                            nl_query=row["nl_query"],
                            cwd=row["cwd"],
                        )
                    )
            else:
                # Fallback: LIKE-based fuzzy search
                words = nl_query.lower().split()
                if words:
                    like_clause = " AND ".join("LOWER(nl_query) LIKE ?" for _ in words)
                    like_params = [f"%{w}%" for w in words]
                    like_results = conn.execute(
                        f"""SELECT shell_cmd, success_count, last_used, nl_query, cwd
                            FROM command_patterns WHERE {like_clause}
                            ORDER BY success_count DESC, last_used DESC LIMIT ?""",  # noqa: S608
                        [*like_params, limit],
                    ).fetchall()
                    for row in like_results:
                        matches.append(
                            PatternMatch(
                                command=row["shell_cmd"],
                                confidence=min(0.7, 0.3 + (row["success_count"] * 0.05)),
                                success_count=row["success_count"],
                                last_used=row["last_used"],
                                nl_query=row["nl_query"],
                                cwd=row["cwd"],
                            )
                        )

            return matches
        finally:
            conn.close()

    def _evict_if_needed(self, conn: sqlite3.Connection) -> None:
        """Remove oldest/least-used patterns if over MAX_PATTERNS."""
        count = conn.execute("SELECT COUNT(*) as c FROM command_patterns").fetchone()["c"]
        if count > MAX_PATTERNS:
            excess = count - MAX_PATTERNS
            conn.execute(
                """DELETE FROM command_patterns WHERE id IN (
                       SELECT id FROM command_patterns
                       ORDER BY success_count ASC, last_used ASC LIMIT ?
                   )""",
                (excess,),
            )

    # ── Layer 2: User Corrections ────────────────────────────────────────────

    def save_correction(self, nl_query: str, rejected_cmd: str, correct_cmd: str) -> None:
        """Save a user correction (rejected command → correct command)."""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO corrections (nl_query, rejected_cmd, correct_cmd, timestamp) VALUES (?, ?, ?, ?)",
                (nl_query, rejected_cmd, correct_cmd, time.time()),
            )
            # Also save the correction as a pattern for future use
            conn.commit()
        finally:
            conn.close()
        # Save the corrected command as a pattern
        self.save_pattern(nl_query, correct_cmd)

    # ── Layer 3: Error Patterns ──────────────────────────────────────────────

    def save_error(self, shell_cmd: str, error_output: str, cwd: str = "") -> None:
        """Save a command that failed with its error output."""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO error_patterns (shell_cmd, error_output, cwd, timestamp) VALUES (?, ?, ?, ?)",
                (shell_cmd, error_output[:2000], cwd, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    def find_fix(self, shell_cmd: str, error_output: str) -> str | None:
        """Find a known fix for a failed command."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT fix_cmd FROM error_patterns
                   WHERE shell_cmd = ? AND fix_cmd != ''
                   ORDER BY timestamp DESC LIMIT 1""",
                (shell_cmd,),
            ).fetchone()
            return row["fix_cmd"] if row else None
        finally:
            conn.close()

    # ── Layer 5: Agent Learnings ─────────────────────────────────────────────

    def save_agent_result(
        self, task_type: str, agent_name: str, success: bool, latency_ms: int = 0
    ) -> None:
        """Record which agent handled a task type and whether it succeeded."""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO agent_learnings (task_type, agent_name, success, latency_ms, timestamp) VALUES (?, ?, ?, ?, ?)",
                (task_type, agent_name, int(success), latency_ms, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    def best_agent_for(self, task_type: str) -> str | None:
        """Find the historically best agent for a task type."""
        conn = self._get_conn()
        try:
            # Look for agents with >70% success rate and at least 3 uses for similar tasks
            words = task_type.lower().split()
            if not words:
                return None
            like_clause = " OR ".join("LOWER(task_type) LIKE ?" for _ in words)
            like_params = [f"%{w}%" for w in words]
            row = conn.execute(
                f"""SELECT agent_name,
                           SUM(success) as wins,
                           COUNT(*) as total,
                           AVG(latency_ms) as avg_latency
                    FROM agent_learnings
                    WHERE {like_clause}
                    GROUP BY agent_name
                    HAVING total >= 3 AND (CAST(wins AS REAL) / total) > 0.7
                    ORDER BY wins DESC, avg_latency ASC
                    LIMIT 1""",  # noqa: S608
                like_params,
            ).fetchone()
            return row["agent_name"] if row else None
        finally:
            conn.close()

    # ── Layer 6: Session Context ─────────────────────────────────────────────

    def save_session(self, session_id: str, cwd: str, recent_cmds: list[str]) -> None:
        """Save session context."""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions (session_id, cwd, recent_cmds, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, cwd, json.dumps(recent_cmds), time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_context(self, cwd: str | None = None, limit: int = 10) -> list[dict]:
        """Get recent successful commands, optionally filtered by directory."""
        conn = self._get_conn()
        try:
            if cwd:
                rows = conn.execute(
                    """SELECT nl_query, shell_cmd, cwd
                       FROM command_patterns WHERE cwd = ?
                       ORDER BY last_used DESC LIMIT ?""",
                    (cwd, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT nl_query, shell_cmd, cwd
                       FROM command_patterns
                       ORDER BY last_used DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            return [{"query": r["nl_query"], "command": r["shell_cmd"], "cwd": r["cwd"]} for r in rows]
        finally:
            conn.close()

    # ── Management ───────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        """Return counts for each layer."""
        conn = self._get_conn()
        try:
            return {
                "patterns": conn.execute("SELECT COUNT(*) as c FROM command_patterns").fetchone()["c"],
                "corrections": conn.execute("SELECT COUNT(*) as c FROM corrections").fetchone()["c"],
                "errors": conn.execute("SELECT COUNT(*) as c FROM error_patterns").fetchone()["c"],
                "agent_learnings": conn.execute("SELECT COUNT(*) as c FROM agent_learnings").fetchone()["c"],
                "sessions": conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"],
            }
        finally:
            conn.close()

    def top_patterns(self, limit: int = 20) -> list[dict]:
        """Return the most-used command patterns."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT nl_query, shell_cmd, success_count, last_used
                   FROM command_patterns
                   ORDER BY success_count DESC, last_used DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                {
                    "query": r["nl_query"],
                    "command": r["shell_cmd"],
                    "uses": r["success_count"],
                    "last_used": r["last_used"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def export_json(self) -> str:
        """Export all patterns as JSON for sharing/backup."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT nl_query, shell_cmd, success_count, cwd, os_name FROM command_patterns"
            ).fetchall()
            data = [
                {
                    "query": r["nl_query"],
                    "command": r["shell_cmd"],
                    "uses": r["success_count"],
                    "cwd": r["cwd"],
                    "os": r["os_name"],
                }
                for r in rows
            ]
            return json.dumps(data, indent=2)
        finally:
            conn.close()

    def import_json(self, json_str: str) -> int:
        """Import patterns from JSON. Returns count of imported patterns."""
        data = json.loads(json_str)
        count = 0
        for item in data:
            query = item.get("query", "")
            cmd = item.get("command", "")
            if query and cmd:
                self.save_pattern(query, cmd, item.get("cwd", ""), item.get("os", ""))
                count += 1
        return count

    def clear(self) -> None:
        """Reset the entire knowledge database."""
        conn = self._get_conn()
        try:
            for table in ("command_patterns", "corrections", "error_patterns", "agent_learnings", "sessions"):
                conn.execute(f"DELETE FROM {table}")  # noqa: S608
            if self._has_fts5:
                conn.execute("DELETE FROM patterns_fts")
            conn.commit()
        finally:
            conn.close()
