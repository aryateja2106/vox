"""Tests for voice module (unit tests with mocked dependencies)."""

import io
import wave
from unittest.mock import patch

from vox.config import VoxConfig


def _make_wav_bytes(num_frames: int = 1600, sample_rate: int = 16000) -> bytes:
    """Generate minimal WAV bytes for testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


def test_transcribe_bytes_empty():
    from vox.voice.asr import transcribe_bytes

    assert transcribe_bytes(b"") is None


@patch("vox.voice.asr.transcribe_file")
def test_transcribe_bytes_delegates(mock_tf):
    from vox.voice.asr import transcribe_bytes

    mock_tf.return_value = "hello world"
    result = transcribe_bytes(_make_wav_bytes())
    assert result == "hello world"
    mock_tf.assert_called_once()


@patch("vox.voice.asr.transcribe_bytes")
@patch("vox.voice.recorder.record_until_silence")
def test_transcribe_mic_flow(mock_record, mock_tb):
    from vox.voice.asr import transcribe_mic

    mock_record.return_value = _make_wav_bytes()
    mock_tb.return_value = "test transcription"
    result = transcribe_mic(VoxConfig())
    assert result == "test transcription"


def test_voice_config_defaults():
    cfg = VoxConfig()
    assert "parakeet" in cfg.voice.asr_model
    assert "Kokoro" in cfg.voice.tts_model
    assert cfg.voice.tts_voice == "am_adam"
