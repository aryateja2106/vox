<coding_guidelines>
# Vox — Personal Terminal Agent

## Build & Test
```bash
uv sync
uv run ruff check src/ tests/
uv run pytest tests/ -v
uv run python -m vox
```

## Voice extras (optional, requires Apple Silicon)
```bash
uv sync --extra voice
```

## Architecture
- `src/vox/cli.py` — Subcommand dispatcher: REPL, listen, speak, agent, config
- `src/vox/engine.py` — Ollama API client, response cleaning, general LLM queries
- `src/vox/config.py` — TOML config (~/.config/vox/config.toml) with env overrides
- `src/vox/voice/recorder.py` — Microphone capture via sounddevice
- `src/vox/voice/asr.py` — Speech-to-text (Parakeet 0.6B via mlx-audio)
- `src/vox/voice/tts.py` — Text-to-speech (Kokoro 82M via mlx-audio)
- `src/vox/agents/base.py` — Base agent interface with subprocess execution
- `src/vox/agents/router.py` — Auto-route tasks to best installed agent via LLM
- `src/vox/agents/{claude,codex,gemini,amp,droid}.py` — Headless agent wrappers
- `scripts/finetune/` — Dataset building and LoRA fine-tuning pipeline
- `install.sh` / `uninstall.sh` — curl-installable scripts
- `docs/index.html` — GitHub Pages landing

## Backend
Ollama API (local inference, no cloud). Default model: qwen2.5-coder:0.5b.
Voice: mlx-audio (Parakeet ASR, Kokoro TTS) on Apple Silicon.
Agents: auto-discovers claude, codex, gemini, amp, droid in PATH.

## CLI
```
vox                        # Interactive REPL
vox "find large files"     # Single NL-to-shell
vox listen                 # Voice → shell command
vox speak "hello"          # Text-to-speech
vox agent "fix tests"      # Delegate to AI agent (auto-routed)
vox agent --list           # Show detected agents
vox agent --use claude "x" # Force specific agent
vox config init            # Create config template
vox config show            # Display current config
```

## Conventions
- Python 3.10+, ruff for lint/format
- Keep core dependencies minimal (httpx, rich)
- Voice/finetune deps are optional extras
- All shell commands single-line, no heredocs
</coding_guidelines>
