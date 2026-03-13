"""Text-to-speech using mlx-audio (Kokoro, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vox.config import VoxConfig

SAMPLE_RATE = 24000


def speak_text(text: str, cfg: VoxConfig | None = None, save_path: str | None = None) -> None:
    """Generate speech from text and play it (or save to file)."""
    import sounddevice as sd

    model_name = cfg.voice.tts_model if cfg else "mlx-community/Kokoro-82M-bf16"
    voice = cfg.voice.tts_voice if cfg else "am_adam"

    from pathlib import Path

    from mlx_audio.tts.utils import load_model

    model = load_model(Path(model_name))

    audio_segments = []
    for result in model.generate(text=text, voice=voice):
        audio_segments.append(result.audio)

    if not audio_segments:
        return

    import mlx.core as mx
    import numpy as np

    audio = mx.concatenate(audio_segments, axis=0)
    audio_np = np.array(audio, dtype=np.float32)

    if save_path:
        _save_wav(audio_np, save_path)
        return

    sd.play(audio_np, samplerate=SAMPLE_RATE, blocking=True)


def _save_wav(audio_np: Any, path: str, sample_rate: int = SAMPLE_RATE) -> None:
    """Save numpy audio array as WAV file."""
    import wave

    import numpy as np

    audio_np = np.clip(audio_np, -1.0, 1.0)
    audio_int16 = (audio_np * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
