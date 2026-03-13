"""Tests for the configuration system."""

import os
from pathlib import Path

from vox.config import (
    CONFIG_TEMPLATE,
    VoxConfig,
    _apply_env_overrides,
    _apply_toml,
    load_config,
)


def test_default_config():
    cfg = VoxConfig()
    assert cfg.model.name == "qwen2.5-coder:0.5b"
    assert cfg.model.provider == "ollama"
    assert cfg.model.api_url == "http://localhost:11434"
    assert cfg.model.temperature == 0.1
    assert cfg.voice.asr_model == "mlx-community/parakeet-tdt-0.6b-v3"
    assert cfg.voice.tts_model == "mlx-community/Kokoro-82M-bf16"
    assert cfg.agents.auto_route is True
    assert cfg.ui.confirm_before_run is True


def test_env_overrides():
    cfg = VoxConfig()
    os.environ["VOX_MODEL"] = "test-model"
    os.environ["VOX_TEMPERATURE"] = "0.5"
    os.environ["VOX_CONFIRM"] = "false"
    try:
        _apply_env_overrides(cfg)
        assert cfg.model.name == "test-model"
        assert cfg.model.temperature == 0.5
        assert cfg.ui.confirm_before_run is False
    finally:
        del os.environ["VOX_MODEL"]
        del os.environ["VOX_TEMPERATURE"]
        del os.environ["VOX_CONFIRM"]


def test_apply_toml():
    cfg = VoxConfig()
    data = {
        "model": {"name": "custom-model", "temperature": 0.7},
        "agents": {"preferred": "codex", "auto_route": False},
    }
    _apply_toml(cfg, data)
    assert cfg.model.name == "custom-model"
    assert cfg.model.temperature == 0.7
    assert cfg.agents.preferred == "codex"
    assert cfg.agents.auto_route is False
    assert cfg.model.provider == "ollama"


def test_load_config_no_file():
    cfg = load_config(Path("/nonexistent/config.toml"))
    assert cfg.model.name == "qwen2.5-coder:0.5b"


def test_config_template_is_valid_toml():
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib

    data = tomllib.loads(CONFIG_TEMPLATE)
    assert "model" in data
    assert "voice" in data
    assert "agents" in data
    assert "ui" in data
