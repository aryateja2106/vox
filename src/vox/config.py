"""Vox configuration — TOML config file with env var overrides."""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

CONFIG_DIR = Path.home() / ".config" / "vox"
CONFIG_FILE = CONFIG_DIR / "config.toml"

CONFIG_TEMPLATE = """\
# Vox configuration — ~/.config/vox/config.toml

[model]
# name = "qwen2.5-coder:0.5b"
# provider = "ollama"          # "ollama" or "mlx"
# api_url = "http://localhost:11434"
# temperature = 0.1

[voice]
# asr_model = "mlx-community/parakeet-tdt-0.6b-v3"
# tts_model = "mlx-community/Kokoro-82M-bf16"
# tts_voice = "am_adam"
# input_device = 0

[agents]
# auto_route = true
# preferred = "claude"
# claude_path = ""
# codex_path = ""
# gemini_path = ""
# amp_path = ""
# droid_path = ""

[ui]
# theme = "monokai"
# confirm_before_run = true
# speak_responses = false
"""


@dataclass
class ModelConfig:
    name: str = "qwen2.5-coder:0.5b"
    provider: str = "ollama"
    api_url: str = "http://localhost:11434"
    temperature: float = 0.1


@dataclass
class VoiceConfig:
    asr_model: str = "mlx-community/parakeet-tdt-0.6b-v3"
    tts_model: str = "mlx-community/Kokoro-82M-bf16"
    tts_voice: str = "am_adam"
    input_device: int = 0


@dataclass
class AgentsConfig:
    auto_route: bool = True
    preferred: str = "claude"
    claude_path: str = ""
    codex_path: str = ""
    gemini_path: str = ""
    amp_path: str = ""
    droid_path: str = ""


@dataclass
class UIConfig:
    theme: str = "monokai"
    confirm_before_run: bool = True
    speak_responses: bool = False


@dataclass
class VoxConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def _apply_env_overrides(cfg: VoxConfig) -> None:
    """Override config values with VOX_* environment variables."""
    env_map = {
        "VOX_MODEL": ("model", "name"),
        "VOX_PROVIDER": ("model", "provider"),
        "VOX_API_URL": ("model", "api_url"),
        "VOX_TEMPERATURE": ("model", "temperature"),
        "VOX_ASR_MODEL": ("voice", "asr_model"),
        "VOX_TTS_MODEL": ("voice", "tts_model"),
        "VOX_TTS_VOICE": ("voice", "tts_voice"),
        "VOX_INPUT_DEVICE": ("voice", "input_device"),
        "VOX_AUTO_ROUTE": ("agents", "auto_route"),
        "VOX_PREFERRED_AGENT": ("agents", "preferred"),
        "VOX_THEME": ("ui", "theme"),
        "VOX_CONFIRM": ("ui", "confirm_before_run"),
        "VOX_SPEAK": ("ui", "speak_responses"),
    }
    for env_key, (section, attr) in env_map.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        section_obj = getattr(cfg, section)
        current = getattr(section_obj, attr)
        if isinstance(current, bool):
            setattr(section_obj, attr, val.lower() in ("1", "true", "yes"))
        elif isinstance(current, int):
            with contextlib.suppress(ValueError):
                setattr(section_obj, attr, int(val))
        elif isinstance(current, float):
            with contextlib.suppress(ValueError):
                setattr(section_obj, attr, float(val))
        else:
            setattr(section_obj, attr, val)


def load_config(path: Path | None = None) -> VoxConfig:
    """Load config from TOML file, then apply env var overrides."""
    cfg = VoxConfig()

    search_paths = [
        path,
        Path("vox-config.toml"),
        CONFIG_FILE,
    ]

    for p in search_paths:
        if p and p.is_file():
            with open(p, "rb") as f:
                data = tomllib.load(f)
            _apply_toml(cfg, data)
            break

    _apply_env_overrides(cfg)
    return cfg


def _apply_toml(cfg: VoxConfig, data: dict) -> None:
    """Apply parsed TOML data to config dataclasses."""
    section_map = {
        "model": cfg.model,
        "voice": cfg.voice,
        "agents": cfg.agents,
        "ui": cfg.ui,
    }
    for section_name, section_obj in section_map.items():
        section_data = data.get(section_name, {})
        for key, val in section_data.items():
            if hasattr(section_obj, key):
                setattr(section_obj, key, val)


def init_config() -> Path:
    """Create a config file template. Returns the path."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(CONFIG_TEMPLATE)
    return CONFIG_FILE
