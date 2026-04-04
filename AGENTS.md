# AGENTS.md — Vox

Guidance for AI agents working on the [vox](https://github.com/nl2shell/vox) repository.

---

## Project Overview

**Vox** (v0.3.0) is the voice-powered CLI for the [NL2Shell](https://github.com/nl2shell) organization. It translates natural language into shell commands using a locally-running Ollama model, adds an optional voice pipeline (mic-in, speech-out) on Apple Silicon, and exposes an agent delegation framework that routes coding/research tasks to installed CLI agents (Claude, Codex, Gemini, Amp, Droid).

```
vox > find all python files bigger than 1MB
  find . -name "*.py" -size +1M -type f
  Run it? [Y/n/c]
```

**Package name:** `vox-shell`  
**Entry point:** `vox.cli:main`  
**Python requirement:** 3.10+  
**Key runtime deps:** `httpx`, `rich` (plus optional `mlx-audio`, `sounddevice` for voice)

---

## Repository Layout

```
src/vox/
  __init__.py          # __version__ = "0.3.0"
  cli.py               # Argument parser, REPL, subcommand dispatcher
  engine.py            # OllamaProvider, BaseProvider, translate(), query_llm()
  config.py            # VoxConfig dataclass, TOML loader, VOX_* env overrides
  voice/
    recorder.py        # Microphone capture via sounddevice (silence detection)
    asr.py             # Speech-to-text via mlx-audio Parakeet 0.6B
    tts.py             # Text-to-speech via mlx-audio Kokoro 82M
  agents/
    base.py            # BaseAgent, AgentResult, _exec() subprocess wrapper
    router.py          # discover_agents(), heuristic + LLM routing, route_and_run()
    claude.py          # ClaudeAgent  -- claude -p <task> --allowedTools ...
    codex.py           # CodexAgent   -- codex exec <task>
    gemini.py          # GeminiAgent  -- gemini -p <task>
    amp.py             # AmpAgent     -- amp -p <task>
    droid.py           # DroidAgent   -- droid -p <task>
tests/
  test_cli.py
  test_config.py
  test_engine.py
  test_provider.py
  test_router.py
  test_agents.py
  test_voice.py
  test_wrappers.py
scripts/finetune/      # Dataset building + LoRA fine-tuning pipeline (optional)
docs/index.html        # GitHub Pages landing
install.sh             # curl-installable one-liner
pyproject.toml         # hatchling build, ruff lint, uv-managed deps
```

---

## Build and Test

```bash
# Install all core deps (recommended: uv)
uv sync

# Install with voice support (Apple Silicon only)
uv sync --extra voice

# Install with fine-tuning pipeline
uv sync --extra finetune

# Run all tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Format check
uv run ruff format --check src/

# Run locally
uv run python -m vox
# or after install:
vox
```

No build step required -- `hatchling` packages `src/vox` directly as `vox-shell`.

---

## Architecture

### Request Flow (text mode)

```
User input (NL string)
  -> cli.py: handle_command()
       -> engine.translate()
            -> OllamaProvider.translate()
                 -> POST /api/chat  (Ollama, local)
                 -> clean_response()   # strip code fences, prompts, leading $
       -> is_dangerous()              # 15 regex patterns (rm -rf, sudo, dd, mkfs, ...)
       -> looks_like_shell()          # reject Python/PHP/HTML/JSON responses
       -> print_command()             # Rich syntax-highlighted display
       -> prompt_action()             # Y/n/c (run / skip / copy)
       -> execute_command()           # subprocess.run, shell=True when pipes present
```

### Key Source Files

| File | Responsibility |
|------|----------------|
| `cli.py` | Argument parsing, REPL loop, subcommand dispatch, dangerous-pattern rejection |
| `engine.py` | `BaseProvider` ABC, `OllamaProvider`, `clean_response()`, `get_platform()` |
| `config.py` | `VoxConfig` dataclass tree, TOML loader (`~/.config/vox/config.toml`), env var override map |

### Safety Layer

Fifteen regex patterns block dangerous commands before execution. All 15 live in `cli.py::DANGEROUS_PATTERNS`:

- Recursive deletion: `rm -rf`, `rm -R`
- Privilege escalation: `sudo`
- Disk operations: `dd if=`, `mkfs`, `shred`, `wipefs`, `> /dev/sd*`
- Fork bomb: `:(){`
- Broad permissions: `chmod 777`
- Service disruption: `systemctl stop/disable/mask`, `killall`, `reboot`, `shutdown`, `poweroff`

Dangerous commands are shown with a red warning and always require manual confirmation even when `--execute` / `-x` is set.

Seven `NON_SHELL_PATTERNS` reject responses that look like Python, PHP, HTML, or JSON rather than shell commands.

---

## CLI Reference

```
vox                             # Interactive REPL
vox "find large files"          # Single shot NL-to-shell
vox -x "show free disk space"   # Auto-execute safe commands
vox --model llama3.2 "..."      # Override model
vox --api http://host:11434 "." # Override Ollama URL

vox listen                      # Voice input -> shell (requires voice extras)
vox listen -x                   # Voice input -> auto-execute
vox speak "hello world"         # Text-to-speech

vox agent "fix the failing tests"         # Delegate to best available agent
vox agent --list                          # Show discovered agents in PATH
vox agent --use claude "refactor auth"    # Force a specific agent

vox config init                 # Write ~/.config/vox/config.toml template
vox config show                 # Display current config (TOML, syntax-highlighted)
vox config edit                 # Open config in $EDITOR
vox config path                 # Print config file path
```

Inside the REPL:

```
vox > !<cmd>          # Pass-through: run a raw shell command
vox > !listen         # Voice input (requires voice extras)
vox > !agent <task>   # Delegate to AI agent
vox > !help           # Show REPL help
vox > exit            # Quit
```

---

## Voice Pipeline (Apple Silicon only)

Voice support is an optional extra (`uv sync --extra voice`) that requires `mlx-audio` and `sounddevice`. It only runs on Apple Silicon (MLX framework).

### Pipeline

```
Microphone
  -> recorder.py: record_until_silence()
       sounddevice.RawInputStream at 16 kHz mono int16
       Silence detection: RMS < 500 for 2 consecutive seconds (max 30 s)
       Returns: WAV bytes (in-memory BytesIO)

WAV bytes
  -> asr.py: transcribe_bytes() -> transcribe_file()
       mlx_audio.stt.utils.load() + transcribe()
       Model: mlx-community/parakeet-tdt-0.6b-v3  (Parakeet 0.6B)
       Returns: transcribed text string

Text string
  -> cli.py: handle_command()   (same path as typed input)

Shell command (optional TTS readback)
  -> tts.py: speak_text()
       mlx_audio.tts.utils.load_model()
       Model: mlx-community/Kokoro-82M-bf16  (Kokoro 82M)
       Voice: am_adam (configurable)
       Output: sounddevice.play() at 24 kHz, or save to WAV
```

### Voice Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| `voice.asr_model` | `mlx-community/parakeet-tdt-0.6b-v3` | Parakeet ASR model (HuggingFace repo) |
| `voice.tts_model` | `mlx-community/Kokoro-82M-bf16` | Kokoro TTS model |
| `voice.tts_voice` | `am_adam` | TTS voice preset |
| `voice.input_device` | `0` | sounddevice input device index |

---

## Agent Delegation Framework

### How Routing Works

`route_and_run(task, cfg)` in `agents/router.py` runs in three phases:

1. **Force override** -- if `VOX_PREFERRED_AGENT` env var is set or `--use` flag provided, use that agent unconditionally.
2. **Heuristic routing** (fast, no LLM call) -- keyword matching:
   - `refactor`, `code`, `fix`, `debug`, `implement` -> prefer `claude` or `codex`
   - `research`, `search`, `summarize` -> prefer `gemini`
3. **LLM routing fallback** -- if heuristic does not match and multiple agents are available, ask the local Ollama model to pick the best agent given the task description.

`discover_agents()` scans `PATH` for known binaries via `shutil.which`. Only installed agents are candidates.

### Agent Roster

| Agent | Binary | Best For | Invocation |
|-------|--------|----------|------------|
| `claude` | `claude` | Code refactoring, debugging, architecture | `claude -p <task> --allowedTools Read,Edit,Bash --output-format text` |
| `codex` | `codex` | Code generation, test fixes, CI tasks | `codex exec <task>` |
| `gemini` | `gemini` | Research, summarization, multi-language | `gemini -p <task>` |
| `amp` | `amp` | Codebase search and navigation (Sourcegraph) | `amp -p <task>` |
| `droid` | `droid` | Complex multi-step engineering | `droid -p <task>` |

All agents extend `BaseAgent` and return an `AgentResult(agent, output, exit_code, error)`. Subprocess timeout is 300 seconds.

### Adding a New Agent

1. Create `src/vox/agents/<name>.py` subclassing `BaseAgent`.
2. Set `name`, `binary`, `description` class attributes.
3. Implement `run(cls, task, **kwargs) -> AgentResult` calling `cls._exec(cmd)`.
4. Import and add the class to `ALL_AGENTS` list in `agents/router.py`.

---

## Configuration System

### Resolution Order (highest wins)

```
CLI flags (--model, --api)
  > VOX_* environment variables
  > ~/.config/vox/config.toml
  > ./vox-config.toml   (project-local, checked first after explicit path)
  > Compiled-in defaults (VoxConfig dataclass)
```

### Config File Location

Default: `~/.config/vox/config.toml`  
Generate template: `vox config init`

```toml
[model]
name = "qwen2.5-coder:0.5b"
provider = "ollama"
api_url = "http://localhost:11434"
temperature = 0.1

[voice]
asr_model = "mlx-community/parakeet-tdt-0.6b-v3"
tts_model = "mlx-community/Kokoro-82M-bf16"
tts_voice = "am_adam"
input_device = 0

[agents]
auto_route = true
preferred = "claude"
claude_path = ""
codex_path = ""
gemini_path = ""
amp_path = ""
droid_path = ""

[ui]
theme = "monokai"
confirm_before_run = true
speak_responses = false
```

### Environment Variable Reference

| Variable | Config Key | Type | Description |
|----------|-----------|------|-------------|
| `VOX_MODEL` | `model.name` | str | Ollama model name |
| `VOX_PROVIDER` | `model.provider` | str | Provider type (`ollama`) |
| `VOX_API_URL` | `model.api_url` | str | Ollama API base URL |
| `VOX_TEMPERATURE` | `model.temperature` | float | Inference temperature |
| `VOX_ASR_MODEL` | `voice.asr_model` | str | HuggingFace ASR model repo |
| `VOX_TTS_MODEL` | `voice.tts_model` | str | HuggingFace TTS model repo |
| `VOX_TTS_VOICE` | `voice.tts_voice` | str | TTS voice preset name |
| `VOX_INPUT_DEVICE` | `voice.input_device` | int | sounddevice input device index |
| `VOX_AUTO_ROUTE` | `agents.auto_route` | bool | Enable LLM-based agent routing |
| `VOX_PREFERRED_AGENT` | `agents.preferred` | str | Default agent when routing is off |
| `VOX_THEME` | `ui.theme` | str | Rich syntax highlight theme |
| `VOX_CONFIRM` | `ui.confirm_before_run` | bool | Prompt before executing commands |
| `VOX_SPEAK` | `ui.speak_responses` | bool | Read shell commands aloud via TTS |

Boolean env vars accept `1`, `true`, or `yes` (case-insensitive).

---

## Translation Engine Details

The `OllamaProvider` calls `POST /api/chat` on the local Ollama server with:

- **System prompt:** "You are an expert shell programmer on {platform}. Output ONLY the shell command. No explanations, no markdown, no code fences."
- **Platform detection:** `sys.platform` -> `macOS` / `Linux` / `Windows (PowerShell)` / `Unix`
- **Temperature:** 0.1 (deterministic by default)
- **Max tokens:** 256 (`num_predict`)
- **Timeout:** 30 seconds

`clean_response()` post-processes the raw model output:
- Strips ` ```bash ` / ` ``` ` fences
- Removes leading `$` or `>` prompts
- Removes "Here is the command:" style prefixes
- Strips leading comment lines

Responses longer than 1000 characters are rejected (not a single shell command).

---

## NL2Shell Organization Cross-References

Vox is one of five repos in the NL2Shell organization. The relevant connections:

| Repo | GitHub | Relationship to Vox |
|------|--------|---------------------|
| **nl2shell** | https://github.com/nl2shell/nl2shell | The fine-tuned model Vox calls. Qwen2.5-0.8B trained on 12k+ NL->bash pairs. Pull via `ollama pull nl2shell`. |
| **nl2shell-web** | https://github.com/nl2shell/nl2shell-web | Marketing site / documentation. Links to Vox install script. |
| **sandbox-bash-mcp** | https://github.com/nl2shell/sandbox-bash-mcp | Docker-based bash sandbox exposing an MCP server. Can be used as a safe execution backend instead of running commands directly on the host. |
| **collab** | https://github.com/nl2shell/collab | Desktop app frontend. Uses Vox/NL2Shell under the hood for terminal sessions. |

When testing translation quality, use the nl2shell model: `VOX_MODEL=nl2shell vox "your query"`.

---

## Common Development Tasks

### Run a single test file

```bash
uv run pytest tests/test_engine.py -v
```

### Test the CLI without Ollama (provider mock)

The test suite mocks `OllamaProvider`. See `tests/test_provider.py` for the pattern.

### Add a new dangerous pattern

Add a raw regex string to `DANGEROUS_PATTERNS` in `src/vox/cli.py`. Keep all patterns in the existing list -- do not create a separate file.

### Swap the default model

Either set `VOX_MODEL=<name>` or edit `model.name` in `~/.config/vox/config.toml`. The model must be pulled in Ollama first (`ollama pull <name>`).

### Test voice locally

```bash
uv sync --extra voice
uv run python -c "from vox.voice.tts import speak_text; speak_text('hello from vox')"
```

Requires Apple Silicon. Ollama is not required for voice-only testing.

---

## Linting and Style

- **Linter/formatter:** `ruff` (target Python 3.10, line length 100)
- **Selected rules:** `E`, `W`, `F`, `I`, `N`, `UP`, `B`, `S`, `T20`, `SIM`, `RUF`
- **Ignored:** `T201` (print), `S101` (assert), `S602/S603/S606/S607` (subprocess), `E501` (line length), `S108` (tmp files)
- No type checker enforced in CI yet; `pyproject.toml` has `[tool.ty]` config for `ty` (experimental)

Run before committing:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run pytest tests/ -v
```
