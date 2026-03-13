"""Speech-to-text using mlx-audio (Parakeet, Whisper, etc.)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vox.config import VoxConfig


def transcribe_file(audio_path: str | Path, cfg: VoxConfig | None = None) -> str | None:
    """Transcribe an audio file using the configured ASR model."""
    from mlx_audio.stt.utils import load, transcribe

    model_name = cfg.voice.asr_model if cfg else "mlx-community/parakeet-tdt-0.6b-v3"
    model = load(model_name)
    result = transcribe(str(audio_path), model=model)

    if isinstance(result, dict):
        return result.get("text", "").strip() or None
    if hasattr(result, "text"):
        return result.text.strip() or None
    return str(result).strip() or None


def transcribe_bytes(audio_bytes: bytes, cfg: VoxConfig | None = None) -> str | None:
    """Transcribe WAV bytes using the configured ASR model."""
    if not audio_bytes:
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        return transcribe_file(tmp_path, cfg)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def transcribe_mic(cfg: VoxConfig | None = None) -> str | None:
    """Record from microphone and transcribe."""
    from vox.voice.recorder import record_until_silence

    audio_bytes = record_until_silence(cfg)
    if not audio_bytes:
        return None
    return transcribe_bytes(audio_bytes, cfg)
