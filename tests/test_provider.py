"""Tests for the provider abstraction in engine.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from vox.config import VoxConfig
from vox.engine import (
    DEFAULT_API_URL,
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    BaseProvider,
    OllamaProvider,
    check_ollama,
    clean_response,
    get_platform,
    get_provider,
    query_llm,
    translate,
)

# ---------------------------------------------------------------------------
# VAL-PROV-001: BaseProvider is abstract
# ---------------------------------------------------------------------------


def test_base_provider_is_abstract():
    """BaseProvider inherits from ABC and cannot be instantiated directly."""
    import abc

    assert issubclass(BaseProvider, abc.ABC)
    try:
        BaseProvider()
        raise AssertionError("Should have raised TypeError")
    except TypeError:
        pass


def test_base_provider_has_abstract_methods():
    """BaseProvider declares abstract methods: translate, query, check."""

    # Collect abstract method names from the ABC
    abstracts = set()
    for name in ("translate", "query", "check"):
        method = getattr(BaseProvider, name, None)
        assert method is not None, f"BaseProvider missing method {name}"
        assert getattr(method, "__isabstractmethod__", False), (
            f"{name} is not abstract"
        )
        abstracts.add(name)
    assert abstracts == {"translate", "query", "check"}


# ---------------------------------------------------------------------------
# VAL-PROV-002: OllamaProvider implements BaseProvider
# ---------------------------------------------------------------------------


def test_ollama_provider_is_subclass_of_base():
    """OllamaProvider is a concrete subclass of BaseProvider."""
    assert issubclass(OllamaProvider, BaseProvider)


def test_ollama_provider_instantiates():
    """OllamaProvider can be instantiated with a config."""
    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    assert isinstance(provider, BaseProvider)
    assert isinstance(provider, OllamaProvider)


# ---------------------------------------------------------------------------
# VAL-PROV-003: OllamaProvider.translate sends correct HTTP request
# ---------------------------------------------------------------------------


@patch("vox.engine.httpx.post")
def test_translate_sends_correct_request(mock_post):
    """translate() POSTs to /api/chat with model, system+user messages, stream=False."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": "ls -la"}
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.translate("list files")

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "/api/chat" in url
    payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
    assert payload["model"] == cfg.model.name
    assert payload["stream"] is False
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "list files"
    assert result == "ls -la"


# ---------------------------------------------------------------------------
# VAL-PROV-004: OllamaProvider.translate applies clean_response
# ---------------------------------------------------------------------------


@patch("vox.engine.httpx.post")
def test_translate_applies_clean_response(mock_post):
    """Raw LLM output wrapped in markdown fences is cleaned."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": "```bash\nls -la\n```"}
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.translate("list files")
    assert result == "ls -la"


# ---------------------------------------------------------------------------
# VAL-PROV-005: OllamaProvider.translate handles errors gracefully
# ---------------------------------------------------------------------------


@patch("vox.engine.httpx.post")
def test_translate_connect_error_returns_none(mock_post):
    """ConnectError returns None."""
    mock_post.side_effect = httpx.ConnectError("Connection refused")

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.translate("list files")
    assert result is None


@patch("vox.engine.httpx.post")
def test_translate_404_returns_none(mock_post):
    """404 status returns None with model-not-found message."""
    response = MagicMock()
    response.status_code = 404
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=response
    )
    mock_post.return_value = response

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.translate("list files")
    assert result is None


@patch("vox.engine.httpx.post")
def test_translate_keyboard_interrupt_returns_none(mock_post):
    """KeyboardInterrupt returns None silently."""
    mock_post.side_effect = KeyboardInterrupt()

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.translate("list files")
    assert result is None


@patch("vox.engine.httpx.post")
def test_translate_generic_error_returns_none(mock_post):
    """Other exceptions return None."""
    mock_post.side_effect = RuntimeError("Something went wrong")

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.translate("list files")
    assert result is None


# ---------------------------------------------------------------------------
# VAL-PROV-006: OllamaProvider.query works for general LLM calls
# ---------------------------------------------------------------------------


@patch("vox.engine.httpx.post")
def test_query_returns_content(mock_post):
    """query() returns stripped content from /api/chat."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": "  The answer is 42  "}
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.query("What is the meaning of life?")
    assert result == "The answer is 42"


@patch("vox.engine.httpx.post")
def test_query_with_system_message(mock_post):
    """query() includes optional system message in request."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "message": {"content": "response"}
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.query("prompt", system="You are helpful")

    call_args = mock_post.call_args
    payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
    messages = payload["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are helpful"
    assert messages[1]["role"] == "user"
    assert result == "response"


@patch("vox.engine.httpx.post")
def test_query_error_returns_none(mock_post):
    """query() returns None on error."""
    mock_post.side_effect = RuntimeError("fail")

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    result = provider.query("prompt")
    assert result is None


# ---------------------------------------------------------------------------
# VAL-PROV-007: OllamaProvider.check reports Ollama status
# ---------------------------------------------------------------------------


@patch("vox.engine.httpx.get")
def test_check_ready(mock_get):
    """check() returns 'ready' when model is found in /api/tags."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "models": [{"name": "nl2shell"}]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    assert provider.check() == "ready"


@patch("vox.engine.httpx.get")
def test_check_no_model(mock_get):
    """check() returns 'no_model' when model is not in list."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "models": [{"name": "llama2:7b"}]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    assert provider.check() == "no_model"


@patch("vox.engine.httpx.get")
def test_check_no_ollama(mock_get):
    """check() returns 'no_ollama' when connection fails."""
    mock_get.side_effect = httpx.ConnectError("Connection refused")

    cfg = VoxConfig()
    provider = OllamaProvider(cfg)
    assert provider.check() == "no_ollama"


# ---------------------------------------------------------------------------
# VAL-PROV-008: Factory function selects provider from config
# ---------------------------------------------------------------------------


def test_get_provider_returns_ollama():
    """get_provider(cfg) returns OllamaProvider when provider is 'ollama'."""
    cfg = VoxConfig()
    cfg.model.provider = "ollama"
    provider = get_provider(cfg)
    assert isinstance(provider, OllamaProvider)


def test_get_provider_unknown_raises():
    """get_provider(cfg) raises ValueError for unknown provider."""
    cfg = VoxConfig()
    cfg.model.provider = "unknown_provider"
    try:
        get_provider(cfg)
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "unknown_provider" in str(e)


# ---------------------------------------------------------------------------
# VAL-PROV-009: Module-level functions preserved as backward-compatible wrappers
# ---------------------------------------------------------------------------


def test_module_level_functions_importable():
    """translate, query_llm, check_ollama, clean_response, get_platform are importable."""
    assert callable(translate)
    assert callable(query_llm)
    assert callable(check_ollama)
    assert callable(clean_response)
    assert callable(get_platform)


@patch("vox.engine.httpx.post")
def test_module_translate_delegates_to_provider(mock_post):
    """Module-level translate() delegates to OllamaProvider.translate()."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "pwd"}}
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    result = translate("show current dir")
    assert result == "pwd"


@patch("vox.engine.httpx.get")
def test_module_check_ollama_delegates(mock_get):
    """Module-level check_ollama() works as backward-compatible wrapper."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"models": [{"name": "nl2shell"}]}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = check_ollama()
    assert result == "ready"


# ---------------------------------------------------------------------------
# VAL-PROV-010 / VAL-PROV-011: Existing tests verified separately
# ---------------------------------------------------------------------------

# VAL-CROSS-002: Config provider setting affects engine behavior
# ---------------------------------------------------------------------------


def test_config_provider_setting_affects_factory():
    """Setting model.provider in config changes which provider get_provider returns."""
    cfg = VoxConfig()
    cfg.model.provider = "ollama"
    provider = get_provider(cfg)
    assert isinstance(provider, OllamaProvider)

    cfg2 = VoxConfig()
    cfg2.model.provider = "future_provider"
    try:
        get_provider(cfg2)
        raise AssertionError("Should have raised ValueError for unknown provider")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Utilities unchanged
# ---------------------------------------------------------------------------


def test_utilities_unchanged():
    """SYSTEM_PROMPT, DEFAULT_MODEL, DEFAULT_API_URL are module-level constants."""
    assert isinstance(SYSTEM_PROMPT, str)
    assert "{platform}" in SYSTEM_PROMPT
    assert isinstance(DEFAULT_MODEL, str)
    assert "nl2shell" in DEFAULT_MODEL
    assert isinstance(DEFAULT_API_URL, str)
    assert DEFAULT_API_URL.startswith("http")
