"""Safety detection — dangerous command patterns and non-shell response filtering."""

from __future__ import annotations

import re

DANGEROUS_PATTERNS = [
    r"\brm\s+.*-\w*[rf]\w*",
    r"\brm\s+-\w*R",
    r"\bsudo\b",
    r"\bdd\b\s+if=",
    r"\bmkfs\b",
    r"\bshred\b",
    r"\bwipefs\b",
    r"\b:\(\)\s*\{",
    r"\bchmod\s+777\b",
    r">\s*/dev/sd[a-z]",
    r"\bsystemctl\s+(stop|disable|mask)\b",
    r"\bkillall\b",
    r"\breboot\b",
    r"\bshutdown\b",
    r"\bpoweroff\b",
]

NON_SHELL_PATTERNS = [
    r"^\s*import\s+",
    r"^\s*from\s+\w+\s+import\b",
    r"^\s*def\s+\w+\(",
    r"^\s*class\s+\w+",
    r"^\s*<\?php",
    r"^\s*<html",
    r"^\s*\{\"",
]


def is_dangerous(cmd: str) -> bool:
    """Check if a command matches any dangerous pattern."""
    return any(re.search(p, cmd, re.IGNORECASE) for p in DANGEROUS_PATTERNS)


def looks_like_shell(cmd: str) -> bool:
    """Check if a response looks like a shell command (not Python, PHP, HTML, etc.)."""
    first_line = cmd.split("\n")[0] if cmd else ""
    return not any(re.search(p, first_line) for p in NON_SHELL_PATTERNS)
