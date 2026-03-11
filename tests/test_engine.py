"""Tests for the translation engine."""

from vox.engine import clean_response, get_platform


def test_clean_response_strips_markdown_fences():
    assert clean_response("```bash\nls -la\n```") == "ls -la"
    assert clean_response("```\nfind . -name '*.py'\n```") == "find . -name '*.py'"


def test_clean_response_strips_prompt_chars():
    assert clean_response("$ ls -la") == "ls -la"
    assert clean_response("> git status") == "git status"


def test_clean_response_strips_whitespace():
    assert clean_response("  ls -la  ") == "ls -la"


def test_clean_response_passthrough():
    assert clean_response("find . -name '*.py'") == "find . -name '*.py'"


def test_get_platform_returns_string():
    platform = get_platform()
    assert isinstance(platform, str)
    assert platform in ("macOS", "Linux", "Windows (PowerShell)", "Unix")
