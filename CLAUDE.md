<coding_guidelines>
# Vox — Self-Learning Terminal Agent

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
- `src/vox/cli.py` — Subcommand dispatcher: REPL, listen, speak, agent, learn, config
- `src/vox/engine.py` — Ollama API client, context-enriched prompts, response cleaning
- `src/vox/config.py` — TOML config (~/.config/vox/config.toml) with env overrides
- `src/vox/safety.py` — Dangerous command detection and non-shell response filtering
- `src/vox/executor.py` — Command execution and clipboard utilities
- `src/vox/knowledge.py` — SQLite self-learning store (6 context layers)
- `src/vox/voice/recorder.py` — Microphone capture via sounddevice
- `src/vox/voice/asr.py` — Speech-to-text (Parakeet 0.6B via mlx-audio)
- `src/vox/voice/tts.py` — Text-to-speech (Kokoro 82M via mlx-audio)
- `src/vox/agents/base.py` — Base agent interface with subprocess execution
- `src/vox/agents/router.py` — Auto-route tasks to best installed agent via LLM
- `src/vox/agents/{claude,codex,gemini,amp,droid}.py` — Headless agent wrappers
- `scripts/finetune/` — Dataset building and LoRA fine-tuning pipeline

## Self-Learning (knowledge.py)
SQLite store at ~/.config/vox/knowledge.db with 6 layers:
1. Command patterns — validated NL-to-shell mappings (FTS5 indexed)
2. User corrections — rejected commands + corrected versions
3. Error patterns — commands that failed + error output
5. Agent learnings — which agent handles which task best
6. Session context — directory-aware recent commands

After 3+ successful uses, a pattern is served from cache (skipping LLM).

## Backend
Ollama API (local inference, no cloud). Default model: qwen2.5-coder:0.5b.
Voice: mlx-audio (Parakeet ASR, Kokoro TTS) on Apple Silicon.
Agents: auto-discovers claude, codex, gemini, amp, droid in PATH.

## CLI
```
vox                        # Interactive REPL
vox "find large files"     # Single NL-to-shell
vox listen                 # Voice -> shell command
vox speak "hello"          # Text-to-speech
vox agent "fix tests"      # Delegate to AI agent (auto-routed)
vox agent --list           # Show detected agents
vox learn show             # Show top learned patterns
vox learn stats            # Knowledge store statistics
vox learn export -f p.json # Export patterns
vox config init            # Create config template
```

## Conventions
- Python 3.10+, ruff for lint/format
- Keep core dependencies minimal (httpx, rich, sqlite3)
- Voice/finetune deps are optional extras
- All shell commands single-line, no heredocs
</coding_guidelines>
