"""Microphone recording with sounddevice."""

from __future__ import annotations

import io
import queue
import wave
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vox.config import VoxConfig

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
SILENCE_THRESHOLD = 500
SILENCE_DURATION = 2.0


def record_until_silence(
    cfg: VoxConfig | None = None,
    max_seconds: float = 30.0,
) -> bytes:
    """Record from microphone until silence is detected or max duration. Returns WAV bytes."""
    import numpy as np
    import sounddevice as sd

    device = cfg.voice.input_device if cfg else 0
    audio_queue: queue.Queue[bytes] = queue.Queue()

    def callback(indata, frames, time_info, status):
        audio_queue.put(bytes(indata))

    frames_list: list[bytes] = []
    silent_chunks = 0
    chunk_duration = 0.1
    chunks_for_silence = int(SILENCE_DURATION / chunk_duration)
    max_chunks = int(max_seconds / chunk_duration)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=int(SAMPLE_RATE * chunk_duration),
        device=device if device else None,
        callback=callback,
    ):
        for _ in range(max_chunks):
            try:
                data = audio_queue.get(timeout=chunk_duration + 0.5)
            except queue.Empty:
                continue

            frames_list.append(data)

            audio_data = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))

            if rms < SILENCE_THRESHOLD:
                silent_chunks += 1
            else:
                silent_chunks = 0

            if silent_chunks >= chunks_for_silence and len(frames_list) > chunks_for_silence:
                break

    if not frames_list:
        return b""

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames_list))

    return buf.getvalue()
