# Vox — Talk to your terminal

## Build & Test
```bash
uv sync
uv run ruff check src/
uv run python -m vox
```

## Architecture
- `src/vox/cli.py` — REPL + single-command mode, Rich UI
- `src/vox/engine.py` — Ollama API client, response cleaning
- `install.sh` / `uninstall.sh` — curl-installable scripts
- `docs/index.html` — GitHub Pages landing

## Backend
Ollama API (local inference, no cloud). Model: nl2shell (custom fine-tuned Qwen3.5-0.8B).
Fallback: any Ollama model via `--model` flag.

## Conventions
- Python 3.9+, ruff for lint/format
- Keep dependencies minimal (httpx, rich)
- All shell commands single-line, no heredocs
