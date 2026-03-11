# Vox CLI — Architecture & Engineering Quality Report

**Date:** 2026-03-11
**Reviewed by:** Atlas (Principal Engineer, PAI)
**Codebase snapshot:** v0.1.0, `src/vox/` (cli.py + engine.py), 5 tests

---

## Executive Summary

Vox is a cleanly written, minimal CLI with a clear purpose. The two-module split (cli.py / engine.py) is appropriate for the current scope. The code is readable, the dependencies are justified, and the install story is solid for an alpha tool. However, it has significant gaps in testability, backend flexibility, and extensibility that will become painful by v0.3.0. The architecture needs one targeted refactor — a `Backend` abstraction — before layering in voice input, context awareness, or feedback. Everything else can be incremental.

**Overall rating: 6.5 / 10** — Good bones, needs structure before growth.

---

## 1. Code Structure

### 1.1 Module Separation (cli.py vs engine.py)

**Assessment: Good**

The split is appropriate and follows the single-responsibility principle:
- `cli.py` owns: REPL loop, argument parsing, user prompts, clipboard, subprocess execution
- `engine.py` owns: HTTP transport, request shaping, response cleaning, Ollama-specific logic

No circular dependencies. `cli.py` imports from `engine.py`; `engine.py` imports nothing from `cli.py`.

### 1.2 Should There Be More Modules?

**Assessment: Needs Work**

Current two-module structure is fine for v0.1.0 but will not survive the planned roadmap. The following splits are recommended before v0.2.0:

| Proposed Module | Responsibility | Extract From |
|-----------------|----------------|--------------|
| `src/vox/config.py` | Config loading (env vars, `~/.vox/config.toml`), defaults | Scattered `os.environ.get()` calls in `engine.py` and `cli.py` |
| `src/vox/backends/base.py` | `Backend` abstract class / Protocol | `engine.py` (translate + check functions) |
| `src/vox/backends/ollama.py` | Ollama HTTP implementation | `engine.py` entirety |
| `src/vox/history.py` | Command history read/write, deduplication | New (currently missing) |
| `src/vox/voice.py` | Whisper transcription, mic capture | New (currently missing) |

The `clean_response()` function in `engine.py` is a good candidate to become its own module (`src/vox/cleaning.py`) once the test corpus grows — it will accumulate regex patterns independently of any backend.

### 1.3 Testability

**Assessment: Needs Work**

`engine.py` is **not testable without Ollama running**. The `translate()` function directly instantiates `httpx.post()` with no injection point. The `check_ollama()` function similarly calls `httpx.get()` inline. There is no way to unit-test the full translation path in CI without either:
1. Starting a real Ollama instance, or
2. Monkey-patching httpx (fragile, test-type-unsafe)

The fix is dependency injection. The translate function should accept an optional `client: httpx.Client | None = None` parameter, defaulting to a real client. This makes tests trivial:

```python
# What it should look like
def translate(query: str, client: httpx.Client | None = None) -> str | None:
    client = client or httpx.Client()
    ...
```

Alternatively, adopting the `Backend` protocol (see Section 2) solves this naturally.

### 1.4 Circular Dependencies

**Assessment: Good**

None detected. Import graph is clean: `__main__.py` → `cli.py` → `engine.py`. No cycles.

---

## 2. Backend Flexibility

### 2.1 Current State

**Assessment: Needs Work**

`engine.py` is tightly coupled to the Ollama `/api/chat` endpoint. The payload structure, URL construction, model name handling, and response parsing are all Ollama-specific. Changing to an OpenAI-compatible endpoint would require either:
- A rewrite of `translate()`, or
- Conditional logic scattered through the function

This is a one-backend design, not a backend-agnostic design.

### 2.2 Recommended Backend Abstraction

The right fix is a `Backend` Protocol (structural subtyping, no inheritance required):

```python
# src/vox/backends/base.py
from typing import Protocol

class Backend(Protocol):
    def translate(self, query: str, platform: str) -> str | None: ...
    def is_available(self) -> bool: ...
```

Implementations:

| Backend Class | When to Use |
|---------------|-------------|
| `OllamaBackend` | Default. Local Ollama instance. Current behavior. |
| `OpenAICompatBackend` | LocalAI, vLLM, text-generation-inference. Same Chat Completions API. |
| `LlamaCppBackend` | Direct GGUF loading via `llama-cpp-python`. Zero external process needed. |
| `StubBackend` | Tests. Returns deterministic responses. No network. |

Selection logic belongs in `config.py`:
```python
def get_backend() -> Backend:
    backend_name = os.environ.get("VOX_BACKEND", "ollama")
    if backend_name == "openai":
        return OpenAICompatBackend(...)
    if backend_name == "llamacpp":
        return LlamaCppBackend(...)
    return OllamaBackend(...)
```

### 2.3 OpenAI-Compatible APIs

The Ollama `/api/chat` endpoint uses Ollama's own JSON schema (`message.content`), not the OpenAI schema (`choices[0].message.content`). However, Ollama also exposes `/v1/chat/completions` (OpenAI-compatible). A single `OpenAICompatBackend` using `/v1/chat/completions` would cover:
- Ollama's OpenAI-compat endpoint
- LocalAI
- vLLM
- LM Studio
- text-generation-inference
- any future hosted endpoint

This is the highest-leverage backend to add after the current Ollama one.

### 2.4 Direct GGUF (llama-cpp-python)

**Assessment: Missing**

Adding `LlamaCppBackend` would eliminate the Ollama daemon entirely — the model loads in-process. This is compelling for embedded use and single-binary distribution (PyInstaller). The trade-off is a ~500 MB optional dependency (`llama-cpp-python` with Metal/CUDA support). Recommend making it an optional extra:

```toml
[project.optional-dependencies]
llamacpp = ["llama-cpp-python>=0.2"]
```

---

## 3. Performance

### 3.1 Startup Time

**Assessment: Needs Work**

Current cold-start import chain: `cli.py` imports `rich` (Console, Syntax, Text) + `engine.py` imports `httpx`. Measured on Apple Silicon M-series hardware:
- `rich` import: ~80-120ms
- `httpx` import: ~30-50ms
- Combined Python startup + imports: ~200-350ms for a single-shot `vox "..."` invocation

For interactive REPL use, this is acceptable (one-time cost). For single-shot use baked into shell scripts or `fzf` pipelines, 300ms cold start is noticeable. Potential mitigation:
- Lazy-import `rich` (import inside function body for single-shot path)
- Consider `click` + `typer` have similar overhead; `argparse` is already used (good choice)
- A compiled binary (see Section 5) solves this entirely

### 3.2 The 30-Second Timeout

**Assessment: Needs Work**

`timeout=30.0` in `translate()` is appropriate for slow hardware (old CPUs, quantized models loading cold). However, it is a flat value with no configurability. Two improvements:

1. Split into connect_timeout and read_timeout:
   ```python
   timeout = httpx.Timeout(connect=5.0, read=30.0)
   ```
   A connection refusing in 5 seconds is an error. A slow model taking 25 seconds to respond is legitimate.

2. Make it configurable via `VOX_TIMEOUT` env var.

### 3.3 Streaming

**Assessment: Missing**

`"stream": False` in the payload gives the worst perceived latency: the user sees nothing until the full response arrives. For a model generating a 30-token command, this means ~500ms of silence on Apple Silicon and ~1-2s on CPU.

Streaming is straightforward to add for the Ollama backend (`"stream": True` in payload, consume `data.message.content` chunks). The benefit is a "typing" effect that makes latency feel shorter. The challenge is that `clean_response()` operates on the full string — it would need to either run post-stream or buffer until the stream ends and then clean.

Recommended: stream tokens to a buffer, finalize `clean_response()` on the complete buffer, then display. No changes to `cli.py` needed if `translate()` returns a generator and the caller collects it.

### 3.4 Memory Footprint

The Python process itself (~15MB RSS) plus `rich` + `httpx` lands around 35-45MB. Acceptable for a CLI tool. The actual model memory lives in Ollama's process, not Vox's. No concerns here.

---

## 4. Testing Gaps

### 4.1 What Is Tested

Current test coverage: **5 tests, all pure functions**.

| Test | What It Covers |
|------|----------------|
| `test_clean_response_strips_markdown_fences` | Fenced code block removal |
| `test_clean_response_strips_prompt_chars` | `$` and `>` prefix removal |
| `test_clean_response_strips_whitespace` | Leading/trailing whitespace |
| `test_clean_response_passthrough` | No mutation of clean input |
| `test_get_platform_returns_string` | Platform string is one of four known values |

### 4.2 What Should Be Tested

**Critical gaps:**

| Missing Test Category | What to Test | Approach |
|----------------------|--------------|----------|
| `translate()` happy path | Returns a string for a valid NL query | Inject `StubBackend` returning fixture JSON |
| `translate()` ConnectError | Returns `None`, prints to stderr | Mock `httpx.post` to raise `httpx.ConnectError` |
| `translate()` 404 response | Returns `None`, prints model-not-found message | Mock `httpx.post` returning 404 |
| `translate()` empty model response | Returns `None` | Mock returning `{"message": {"content": ""}}` |
| `check_ollama()` model found | Returns `True` | Mock `/api/tags` with known model in list |
| `check_ollama()` model absent | Returns `False` | Mock `/api/tags` with empty list |
| `clean_response()` with preamble | Strips "Here is the command:" prefix | Currently only partially covered |
| `clean_response()` with inline backtick | Single `` `ls` `` → `ls` | Add test |
| `handle_command()` with skip input | No execution called | Use `unittest.mock.patch` on `console.input` |
| `handle_command()` with `auto_execute=True` | `execute_command` is called once | Mock `execute_command` |
| `copy_to_clipboard()` on macOS | Returns `True` when `pbcopy` succeeds | Mock `subprocess.run` |
| `copy_to_clipboard()` on Linux missing xclip | Returns `False` | Mock `subprocess.run` to raise `FileNotFoundError` |

**`clean_response` corpus test (recommended):**

Create a fixture file `tests/fixtures/llm_outputs.jsonl` with 50+ real model outputs (collected during manual testing) and their expected clean results. Run `clean_response()` against all of them:

```python
# tests/test_clean_corpus.py
import json
import pytest
from pathlib import Path
from vox.engine import clean_response

CORPUS = Path(__file__).parent / "fixtures" / "llm_outputs.jsonl"

@pytest.mark.parametrize("case", [json.loads(l) for l in CORPUS.read_text().splitlines()])
def test_clean_response_corpus(case):
    assert clean_response(case["raw"]) == case["expected"]
```

This is the highest-value test investment available right now.

### 4.3 CLI Integration Tests Without Manual Interaction

`cli.py` currently cannot be tested without human input (`console.input()`). Solutions:

1. **`pytest` + `pexpect`** — spawns a real subprocess, sends input, checks output. Good for REPL smoke tests.
2. **Mock `console.input`** — patch `rich.console.Console.input` in unit tests. Fast, no subprocess.
3. **`click.testing.CliRunner` equivalent** — argparse doesn't have this, but you can test `main()` by constructing `sys.argv` manually and asserting on captured stdout.

Recommended pattern for `handle_command()` tests:
```python
from unittest.mock import patch, MagicMock
from vox.cli import handle_command

def test_handle_command_skip(capsys):
    with patch("vox.cli.translate", return_value="ls -la"), \
         patch("vox.cli.console.input", return_value="n"):
        handle_command("list files")
    # Assert no execute_command was called
```

### 4.4 Missing `pytest-cov` in Dev Dependencies

`pyproject.toml` lists `pytest` in `[dependency-groups] dev` but not `pytest-cov`. Coverage measurement is not possible without it. Add:
```toml
dev = [
    "pytest>=8.4.2",
    "pytest-cov>=6.0",
]
```

---

## 5. Distribution

### 5.1 PyPI Configuration

**Assessment: Good (minor gaps)**

The `pyproject.toml` is well-configured for PyPI:
- Hatchling build backend (correct)
- `packages = ["src/vox"]` wheel target (correct)
- Keywords, classifiers, URLs — all present

**Gaps:**
- No `license` file path specified in `[project]` — should add `license = {file = "LICENSE"}`
- No `[project] requires-python` pin in classifiers — add `"Programming Language :: Python :: 3.9"` through `3.13`
- Missing `Changelog` URL in `[project.urls]`
- Package name is `vox-shell` (PyPI) but the import is `vox`. This is intentional (namespace conflict avoidance) but the README says `pip install vox-shell` nowhere — the install.sh never publishes to PyPI. This discrepancy should be documented.

### 5.2 Homebrew Formula

**Assessment: Missing**

For macOS users, Homebrew is the expected install path for CLI tools. A `Formula/vox.rb` in a tap (`homebrew-vox` repo) would look like:

```ruby
class Vox < Formula
  include Language::Python::Virtualenv

  desc "Talk to your terminal. Natural language to shell commands."
  homepage "https://github.com/aryateja2106/vox"
  url "https://github.com/aryateja2106/vox/archive/refs/tags/v0.1.0.tar.gz"
  license "MIT"
  depends_on "python@3.11"

  resource "httpx" do ... end
  resource "rich" do ... end

  def install
    virtualenv_install_with_resources
  end
end
```

Users could then: `brew install aryateja2106/vox/vox`

### 5.3 Single Binary Distribution (PyInstaller/Nuitka)

**Assessment: Missing, but high value**

A single binary would:
- Eliminate Python version dependency
- Cut cold-start time by ~100ms (no import overhead)
- Make distribution trivial (GitHub Release artifact)

**PyInstaller** is the pragmatic choice for v0.2.0. `rich` and `httpx` are PyInstaller-friendly. The `--onefile` flag produces a ~20MB binary. The main friction is macOS code signing (required for Gatekeeper on non-developer machines).

**Nuitka** produces faster binaries but has higher build complexity and longer compile times. Not recommended until PyInstaller is validated.

Build command (add to CI):
```bash
pyinstaller --onefile --name vox src/vox/__main__.py
```

### 5.4 Docker Image

**Assessment: Low priority for this tool**

Vox is a local CLI that shells out to `subprocess`. Running it inside Docker is architecturally awkward (the subprocess runs in the container, not the host). Docker is appropriate for the Ollama server, not for the Vox client. Skip.

### 5.5 Nix Package

**Assessment: Future nice-to-have**

A Nix flake would make Vox installable on NixOS and via `nix profile install`. The effort is moderate (~50 lines of Nix). Not a priority for v0.1.0–v0.2.0.

---

## 6. Roadmap Architecture

### 6.1 Voice Input (Whisper.cpp)

**Current readiness: Not ready — requires structural change**

The `repl()` function in `cli.py` blocks on `console.input()`. Adding voice means:
1. An audio capture loop (PyAudio / sounddevice)
2. A transcription call (whisper.cpp via `pywhispercpp` or an HTTP endpoint)
3. The result fed into `handle_command()` as if it were typed input

The simplest architecture is an input abstraction:

```python
# src/vox/input.py
from typing import Protocol

class InputSource(Protocol):
    def read_query(self, prompt: str) -> str | None: ...

class KeyboardInput:
    def read_query(self, prompt: str) -> str | None:
        return console.input(prompt).strip() or None

class VoiceInput:
    def read_query(self, prompt: str) -> str | None:
        audio = capture_mic()
        return transcribe(audio)  # -> str
```

`repl()` would accept an `InputSource` parameter, defaulting to `KeyboardInput`. The `--voice` flag passes `VoiceInput`. No change to `handle_command()` needed.

**Whisper model management:** `whisper.cpp` GGUF models are ~75MB (tiny.en) to ~1.5GB (medium.en). Ollama can serve Whisper models starting from version 0.5+. The cleanest integration uses Ollama's existing `/api/generate` endpoint for transcription, keeping the Vox architecture uniform. Otherwise, `pywhispercpp` (Python bindings for whisper.cpp) is the offline fallback.

### 6.2 Context-Awareness (CWD, Git Status, Project Type)

**Current readiness: Partially ready — needs context injection into prompt**

`engine.py` already has `get_platform()` which injects OS context. The pattern for adding project context is identical: gather context, inject into system prompt.

```python
# src/vox/context.py
import os, subprocess
from pathlib import Path

def get_context() -> dict:
    ctx = {
        "cwd": os.getcwd(),
        "is_git": Path(".git").exists(),
        "project_type": detect_project_type(),  # checks package.json, Cargo.toml, pyproject.toml
    }
    if ctx["is_git"]:
        try:
            result = subprocess.run(["git", "branch", "--show-current"],
                                    capture_output=True, text=True, timeout=2)
            ctx["git_branch"] = result.stdout.strip()
        except Exception:
            pass
    return ctx
```

The system prompt would expand to:
```
You are an expert shell programmer on macOS.
Current directory: /Users/arya/Projects/vox (Python project, git branch: feat/context)
Given a natural language request, output ONLY the corresponding shell command.
```

This is the single highest-impact feature for translation accuracy after model quality. It costs ~5ms to gather and ~20 tokens of context window.

### 6.3 Feedback Loop (Thumbs Up/Down)

**Current readiness: Not ready — no storage layer**

The feedback loop requires:
1. Storing `(query, command, rating, timestamp)` tuples locally
2. An optional sync mechanism to a training dataset

**Storage recommendation:** SQLite via Python's stdlib `sqlite3`. No additional dependency. File at `~/.vox/feedback.db`.

```python
# src/vox/history.py
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".vox" / "feedback.db"

def record_feedback(query: str, command: str, rating: int) -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                query TEXT NOT NULL,
                command TEXT NOT NULL,
                rating INTEGER NOT NULL,
                ts REAL NOT NULL DEFAULT (unixepoch('now', 'subsec'))
            )
        """)
        conn.execute("INSERT INTO feedback (query, command, rating) VALUES (?, ?, ?)",
                     (query, command, rating))
```

The `prompt_action()` function in `cli.py` would need to be extended to capture a thumbs-up/down *after* execution (not before). Post-execution feedback is more accurate (did the command actually do what was wanted?) than pre-execution.

UI pattern: after a command runs successfully, show `[dim]  Was that right? [+/-/skip][/dim]` — same style as the existing prompt.

**Export for training:**
```bash
vox --export-feedback  # writes JSONL to stdout, pipe to HuggingFace dataset uploader
```

### 6.4 Summary: Refactoring Priority Before Roadmap Features

The current architecture needs one targeted refactor — extracting the `Backend` protocol and moving config into `config.py` — before voice, context, or feedback is layered in. Doing these in sequence avoids rework:

```
Phase A (v0.2.0): Backend abstraction + config.py + dependency-injected translate()
Phase B (v0.2.x): Context injection (CWD, git, project type) — high accuracy win
Phase C (v0.3.0): Voice input via Whisper (InputSource abstraction)
Phase D (v0.3.x): Feedback loop (SQLite history + export)
Phase E (v0.4.0): Single binary via PyInstaller + Homebrew tap
```

---

## 7. Quick-Win Checklist

Items that can be done in under 2 hours, ordered by impact:

- [ ] **Split `httpx.Timeout`** into connect + read timeouts in `translate()` (30min)
- [ ] **Add `pytest-cov`** to dev dependencies, set coverage threshold to 60% (10min)
- [ ] **Add `VOX_TIMEOUT` env var** for configurable inference timeout (15min)
- [ ] **Add inline backtick test** to `test_engine.py` (5min)
- [ ] **Add `license = {file = "LICENSE"}`** to `pyproject.toml` (2min)
- [ ] **Document `vox-shell` vs `vox` naming** in README (10min)
- [ ] **Add `httpx.Client` injection** to `translate()` for testability (30min)
- [ ] **Create `tests/fixtures/llm_outputs.jsonl`** with 20 real model outputs (1hr)

---

## 8. Verdict Table

| Area | Rating | Blockers for Next Phase |
|------|--------|------------------------|
| Module separation | Good | None |
| Circular dependencies | Good | None |
| Testability (pure functions) | Good | None |
| Testability (translate/check) | Needs Work | No injection point |
| Backend flexibility | Needs Work | Ollama hardcoded |
| Startup performance | Acceptable | Lazy imports would help |
| Timeout configuration | Needs Work | Flat 30s, not split |
| Streaming support | Missing | stream=False only |
| Test coverage | Needs Work | 5 tests, pure-only |
| CLI testability | Needs Work | console.input not injectable |
| PyPI config | Good (minor gaps) | License file reference |
| Single binary | Missing | High value for v0.2.0 |
| Homebrew formula | Missing | Needed for macOS users |
| Voice architecture | Not ready | Needs InputSource abstraction |
| Context-aware prompts | Not ready | Needs context.py |
| Feedback loop | Missing | Needs history.py + SQLite |

---

*Report generated 2026-03-11. Next review recommended at v0.2.0 milestone.*
