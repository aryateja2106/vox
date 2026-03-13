# Environment

Environment variables, external dependencies, and setup notes.

**What belongs here:** Required env vars, external API keys/services, dependency quirks, platform-specific notes.
**What does NOT belong here:** Service ports/commands (use `.factory/services.yaml`).

---

## Python

- Python >=3.10 (pyproject.toml: requires-python = ">=3.10")
- Build: hatchling
- Package manager: uv (uv.lock present)
- Virtual env: .venv/ in project root

## Dependencies

- Core: httpx>=0.24, rich>=13.0, tomli>=2.0 (py<3.11 only)
- Dev: pytest>=8.4.2
- Optional [voice]: mlx-audio>=0.4, sounddevice>=0.4
- Optional [finetune]: transformers, peft, datasets

## Environment Variables

- VOX_MODEL — override model name
- VOX_PROVIDER — override provider (ollama/mlx)
- VOX_API_URL — override Ollama API URL
- VOX_TEMPERATURE — override temperature
- VOX_AUTO_ROUTE — enable/disable auto routing
- VOX_PREFERRED_AGENT — preferred agent for routing
- VOX_THEME, VOX_CONFIRM, VOX_SPEAK — UI overrides

## External Services

- Ollama on localhost:11434 (pre-existing, not managed by mission)
- All agent binaries discovered via PATH: claude, codex, gemini, amp, droid
