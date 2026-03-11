"""Tests for the translation engine."""

from vox.engine import DEFAULT_MODEL, clean_response, get_platform


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


def test_clean_response_inline_backticks():
    assert clean_response("`ls -la`") == "ls -la"


def test_clean_response_comment_lines():
    assert clean_response("# Create a new branch\ngit checkout -b feature") == "git checkout -b feature"


def test_clean_response_preamble():
    assert clean_response("Here is the command:\nls -la") == "ls -la"


def test_get_platform_returns_string():
    platform = get_platform()
    assert isinstance(platform, str)
    assert platform in ("macOS", "Linux", "Windows (PowerShell)", "Unix")


def test_default_model_is_small_coder():
    assert "coder" in DEFAULT_MODEL or "nl2shell" in DEFAULT_MODEL
