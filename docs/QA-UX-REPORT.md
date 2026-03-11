# Vox CLI — UX & Usability Review

**Date:** 2026-03-11
**Reviewer:** Atlas (Principal Engineer, CloudAGI)
**Version reviewed:** 0.1.0
**Files reviewed:** `src/vox/cli.py`, `src/vox/engine.py`, `README.md`, `install.sh`, `uninstall.sh`, `pyproject.toml`

---

## Severity Legend

| Level | Meaning |
|-------|---------|
| **P0** | Blocker — breaks core functionality or causes silent failure |
| **P1** | Critical — degrades UX significantly; must fix before public launch |
| **P2** | Important — noticeably worse than competitor baseline |
| **P3** | Nice-to-have — polish, parity, or future improvements |

---

## 1. First-Run Experience

### 1.1 Missing Ollama — Error Quality

**Severity: P1**

When Ollama is not running, `check_ollama()` silently returns `False` and the REPL shows:

```
Warning: Ollama not reachable or model not found.
Start Ollama: ollama serve
Pull model:   ollama pull nl2shell
```

The problem: `check_ollama()` catches *all* exceptions in a bare `except Exception` block and returns `False` for both "Ollama not installed" and "Ollama installed but not running." The user receives an identical warning message for two very different situations:

- **Ollama not installed at all** → user needs to install it first, then serve it, then pull the model (3 steps)
- **Ollama installed but not running** → user just needs `ollama serve` (1 step)

The warning conflates both cases and shows both remediation lines unconditionally, which is confusing.

**Suggested fix:**

```python
def check_ollama() -> tuple[bool, str]:
    """Returns (ok, reason) where reason is 'ok' | 'not_running' | 'model_missing'."""
    try:
        r = httpx.get(f"{get_api_url()}/api/tags", timeout=5.0)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        model = get_model()
        if not any(model in m for m in models):
            return False, "model_missing"
        return True, "ok"
    except httpx.ConnectError:
        return False, "not_running"
    except Exception:
        return False, "not_running"
```

Then surface a distinct, actionable message per case in `repl()`.

---

### 1.2 No Guided Setup / First-Run Wizard

**Severity: P1**

When a user runs `vox` for the first time with no model and no Ollama, they hit a wall immediately. The REPL starts, prints a yellow warning, then sits at `vox >` waiting. A new user doesn't know:

1. Is the tool broken, or just not configured?
2. Do they need to install Ollama before *or* after the tool?
3. Why does `nl2shell` not exist on `ollama pull nl2shell`? (The model is not yet published to the Ollama registry.)

There is no "first run detected" state, no wizard, and no fallback suggestion pointing users to an alternative available model (e.g., `llama3.2` or `qwen2.5:0.5b`).

**Suggested fix:** Detect first run via a `~/.config/vox/config.toml` marker. On first run without a working model, print a numbered onboarding sequence and offer to run `ollama pull <fallback>` interactively.

---

### 1.3 Default Model `nl2shell` Not Available on Ollama Registry

**Severity: P0**

The default model is `nl2shell`, but `ollama pull nl2shell` will fail because this model is not published to the Ollama registry yet (it is the custom fine-tuned AryaYT/nl2shell-0.8b on HuggingFace in GGUF format). This means *every new user* gets a broken default.

The `install.sh` script acknowledges this with:
```
When available, pull with: ollama pull nl2shell
For now, use any model: vox --model llama3.2
```

But the REPL startup warning and the README examples still reference `nl2shell` as if it works. This is misleading and will generate immediate user frustration.

**Suggested fix:** Until the model is published to the Ollama registry:
1. Change the default model in `engine.py` to a stable fallback such as `qwen2.5:0.5b` or `llama3.2:1b`
2. OR add a `vox setup` subcommand that checks for the model and guides the user through a manual GGUF import
3. Update README to clearly state the model's current availability status

---

### 1.4 Model Choice Guidance

**Severity: P2**

The README mentions you can use `vox --model llama3.2` but gives no guidance on which models work well for NL-to-shell translation. A user who doesn't have `nl2shell` has no idea whether `phi4`, `mistral`, or `qwen2.5:0.5b` will produce good results. There is no quality guidance or model recommendation table.

**Suggested fix:** Add a "Tested models" section to the README listing models by quality tier (e.g., recommended, acceptable, avoid). Alternatively, add a `vox models` subcommand that lists locally installed Ollama models with a suitability indicator.

---

## 2. REPL Experience

### 2.1 No Command History (Arrow Keys)

**Severity: P1**

The REPL uses `console.input()` from Rich, which does **not** provide readline-style history (up/down arrow navigation). After typing several queries, the user cannot recall a previous query with the up arrow. This is a baseline expectation for any interactive CLI in 2026.

**Suggested fix:** Replace `console.input()` with Python's `input()` wrapped in `readline` on Unix/macOS, or use the `prompt_toolkit` library for a proper input experience with history, multi-line editing, and completion.

```python
import readline  # noqa: F401 — side effect: enables arrow key history in input()

query = input("\x1b[1;36mvox >\x1b[0m ").strip()
```

Or for a richer experience:
```python
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

query = prompt("vox > ", history=FileHistory("~/.config/vox/history"))
```

---

### 2.2 No Tab Completion

**Severity: P3**

There is no tab completion for special commands (`!`, `exit`, `quit`, `:q`) or for common query patterns. This is a polish item but expected in mature CLIs.

**Suggested fix:** `prompt_toolkit` supports custom completers. Add completion for built-in commands and potentially for filesystem paths in queries that mention files.

---

### 2.3 Prompt Visual Design — Adequate but Minimal

**Severity: P3**

The prompt `vox >` is functional and reasonably polished with cyan+bold styling. However it lacks:
- No indicator of the current model being used
- No indicator of connection status (connected/disconnected)
- No spinner or "thinking..." indicator during translation — the REPL hangs silently for up to 30 seconds while waiting for the model

The silent hang during translation is a **P1** issue. On slower hardware or large models, the user sees nothing for 2–30 seconds and has no feedback that the tool is working.

**Suggested fix:**
```python
with console.status("[dim]thinking...[/dim]", spinner="dots"):
    cmd = translate(query)
```

---

### 2.4 No Undo / Correction

**Severity: P2**

If a user runs a command that produces wrong output, there is no "try again" or "rephrase" prompt. After execution, the REPL just returns to `vox >`. There is no way to refine the last query without retyping it.

**Suggested fix:** After a failed execution (non-zero exit code), offer:
```
  exit 1
  Rephrase? [y/N]
```
If yes, pre-fill the prompt with the previous query text (requires `prompt_toolkit`).

---

### 2.5 Error Messages Mix Rich and Stderr

**Severity: P2**

There is an inconsistency in error rendering. `cli.py` uses Rich's `console.print()` for all output, but `engine.py` uses bare `print(..., file=sys.stderr)`. This means:
- Connection errors bypass Rich formatting entirely — no color, no consistent indentation
- The error output can interleave unexpectedly with Rich-formatted content

**Suggested fix:** Pass a `Console` instance (or import the module-level one) into `engine.py`, or raise typed exceptions from `engine.py` and handle presentation entirely in `cli.py`.

---

### 2.6 `!` Raw Pass-Through Has No Output Feedback

**Severity: P2**

The `!` raw command pass-through in the REPL runs the command silently (no echo of what was run, no exit code display on failure). Compare with `handle_command()` which shows the syntax-highlighted command and the exit code.

```python
if query.startswith("!"):
    execute_command(query[1:].strip())  # silent run, no echo
    console.print()
    continue
```

**Suggested fix:** Print the raw command with dimmed styling before executing:
```python
console.print(f"  [dim]$ {query[1:].strip()}[/dim]")
```
And show exit code on non-zero, matching the pattern in `handle_command()`.

---

### 2.7 No `!help` or `?` Built-in Help

**Severity: P1**

Typing `help` or `?` in the REPL sends those strings to the model for translation, which will produce nonsense shell commands. There is no in-REPL help system. A user discovering the tool for the first time has no way to find out about `!` pass-through, `exit`/`:q`, or the `[Y/n/c]` prompt options — unless they already read the README.

**Suggested fix:** Add a `help` built-in that prints a compact command reference:
```
  vox commands:
    !<cmd>        run a shell command directly
    exit / :q     quit vox
    ?             show this help

  At the [Y/n/c] prompt:
    y (enter)     run the command
    n             skip it
    c             copy to clipboard
```

---

## 3. Output Quality

### 3.1 Syntax Highlighting — Good

**Severity: —** (Positive note)

The use of `rich.syntax.Syntax` with `monokai` theme for bash highlighting is well-chosen. The padded code block visually separates the generated command from the surrounding prompt text. This is the strongest UX element in the current implementation.

---

### 3.2 `[Y/n/c]` Prompt — Partially Intuitive

**Severity: P2**

The `[Y/n/c]` prompt is placed immediately after the syntax-highlighted command with only `Run it?` as context. Issues:

1. The meaning of `c` (copy to clipboard) is not explained. First-time users may not know.
2. There is no `e` (explain) option. For a tool that translates NL to shell, not being able to ask "what does this command actually do?" is a major gap.
3. There is no `!` (edit) option to modify the command before running.

**Suggested fix:** Extend the prompt to `[Y/n/c/e/?]` and add:
- `e` — print a plain-English explanation of the command (send command back to the model with an "explain this command" prompt)
- `?` — show the meaning of each option inline

---

### 3.3 No Dangerous Command Detection

**Severity: P1**

There is no detection of dangerous commands. Queries like "delete everything in this folder" or "remove all docker volumes" will produce `rm -rf .` or `docker volume prune -f` and immediately present `Run it? [Y/n/c]` with no extra warning.

Given that the model occasionally hallucinates (e.g., produces `rm -rf /` from an ambiguous query), this is a meaningful safety gap.

**Suggested fix:** Add a `is_dangerous(cmd)` check before the action prompt:

```python
DANGEROUS_PATTERNS = [
    r"\brm\s+(-\S*r\S*\s+|-rf\b)",  # rm -rf variants
    r"\bsudo\b",
    r"\bdd\b.*(of=/dev)",
    r">\s*/dev/(sd|hd|nvme)",
    r"\bdrop\s+database\b",
    r"\bchmod\s+777\s+/",
]

def is_dangerous(cmd: str) -> bool:
    return any(re.search(p, cmd, re.IGNORECASE) for p in DANGEROUS_PATTERNS)
```

When dangerous, print a red warning banner before the `[Y/n/c]` prompt:
```
  [red]Warning: This command is destructive and cannot be undone.[/red]
  Run it? [y/N/c]   (default: N)
```
Note: flip the default to `N` (no) for dangerous commands.

---

### 3.4 No "Explain This Command" Option

**Severity: P2**

As noted in 3.2, there is no way to ask what a generated command does. This is especially important for users who are *learning* the shell. The core value proposition ("stop memorizing flags") implies the user might be unfamiliar with the output.

**Suggested fix:** Add `e` as an option in `prompt_action()`. When selected, call the model again with a system prompt focused on explaining rather than translating:

```python
EXPLAIN_PROMPT = (
    "Explain what this shell command does in 1-2 plain English sentences. "
    "Be concise. No markdown."
)
```

---

### 3.5 "Could Not Translate" — Too Terse

**Severity: P2**

When the model fails to produce a command (empty response after cleaning), the user sees:
```
  Could not translate. Try rephrasing.
```

This is unhelpful. The user doesn't know whether the failure was because:
- The model doesn't understand the query
- The Ollama connection dropped mid-request
- The model produced something that was stripped entirely by `clean_response()`

There is also no suggestion of an alternative phrasing or example.

**Suggested fix:** Show the last query back to the user and offer a rephrasing hint:
```
  Could not generate a command for: "your query here"
  Try being more specific, e.g. "list all .py files in current folder"
```

---

## 4. Comparison with `nlsh` (Competitor)

### Feature Parity Matrix

| Feature | nlsh | vox | Gap |
|---------|------|-----|-----|
| `!api` — switch provider | Yes | `--model` flag (CLI only) | P2: no in-REPL model switching |
| `!help` — in-REPL help | Yes | No | P1 |
| `!cmd` — raw pass-through | Yes | `!<cmd>` | Parity (slightly different syntax) |
| Command history (arrows) | Yes | No | P1 |
| Tab completion | Yes | No | P3 |
| Explain command option | Some versions | No | P2 |
| Dangerous command warning | Some versions | No | P1 |
| In-REPL model change | Yes (`!api`) | No | P2 |
| Cloud model support | Yes | No (intentional) | — |
| Offline / local-only | No | Yes | vox wins |
| Clipboard copy | No | Yes | vox wins |
| Platform detection | No | Yes | vox wins |
| Thinking indicator/spinner | Yes | No | P1 |
| Single-line install | Partial | Yes | vox wins |
| Voice-ready design | No | Yes | vox wins |

---

### What Vox Does Better

1. **100% local inference** — no API keys, no cloud, no privacy risk. `nlsh` requires a cloud API key by default.
2. **Clipboard copy option** — the `c` option in `[Y/n/c]` is genuinely useful and absent in most competitors.
3. **Platform-aware prompting** — the system prompt dynamically includes `macOS` vs `Linux`, which improves translation accuracy (e.g., `pbcopy` vs `xclip`, `brew` vs `apt`).
4. **Minimal dependencies** — only `httpx` and `rich`. `nlsh` has a heavier dependency footprint.
5. **Custom fine-tuned model** — purpose-built for NL-to-shell; general models like `gpt-4o` add latency and cost.
6. **Cleaner LLM response sanitization** — the `clean_response()` function handles markdown fences, inline backticks, `$` prompt prefixes, and preamble strings. This is more robust than most competitors.

---

### What Vox Is Missing vs nlsh

1. **In-REPL `!model <name>`** to switch models without restarting (P2)
2. **In-REPL `!help`** command (P1)
3. **Command history via arrow keys** (P1)
4. **Thinking spinner** (P1)
5. **Dangerous command safeguard** (P1)
6. **"Explain" option at the run prompt** (P2)

---

## 5. Install / Uninstall Experience

### 5.1 Install Script — Good Overall, One Failure Mode

**Severity: P1**

The `install.sh` script has solid logic: it tries `pipx` → `uv tool` → `pip --user` in order of preference, and fails gracefully. However there is one P1 issue: if all three installers fail, the error message is:

```
  ✗ Installation failed. Try manually:
    pip install git+https://github.com/aryateja2106/vox.git
```

This fallback command also requires network access to GitHub and will fail on corporate networks with git proxy restrictions. There is no `pip install vox-shell` fallback pointing to PyPI because the package has not been published yet. A user who hits this dead end has no path forward.

**Suggested fix:** Publish `vox-shell` to PyPI immediately. The `pyproject.toml` is already configured for it. Add `pip install vox-shell` as the primary suggested fallback in the error message once published.

---

### 5.2 `set -euo pipefail` + Silent `2>/dev/null` Pattern

**Severity: P2**

The install script uses `set -euo pipefail` (good practice), but then silences errors with `2>/dev/null` on the installation commands. This means a user who encounters a genuine error (wrong Python, corporate proxy, disk full) gets:

```
  ✗ Installation failed. Try manually: ...
```

...with no error detail. The `2>/dev/null` suppression is too aggressive.

**Suggested fix:** Remove `2>/dev/null` or redirect to a temp log file and display the log on failure:

```bash
LOG=$(mktemp)
pipx install "git+${REPO}" --force 2>"$LOG" && INSTALLED=1 || { cat "$LOG"; INSTALLED=0; }
```

---

### 5.3 Uninstall Script — Package Name Mismatch Risk

**Severity: P1**

The install script installs from git as `vox-shell` (the `pyproject.toml` `name` field). The uninstall script correctly uses `vox-shell`. However, the `install.sh` uses `--force` on `pipx` and `uv`, which means reinstalling always succeeds without warning the user.

More importantly: if the user installed `vox-shell` via `pip --user` (the fallback path), the uninstall script correctly calls `pip uninstall -y vox-shell`. But if the user installed via pipx (the preferred path), `pipx uninstall vox-shell` will work correctly only if they've never run `pipx install` with a different invocation. This is fragile.

Also, uninstall does **not** remove:
- Shell history entries
- `~/.config/vox/` config directory (if created by a future version)
- Shell aliases a user may have added based on docs

**Suggested fix:** Add cleanup of config directories and print a note about manually removing any shell aliases:
```bash
rm -rf ~/.config/vox 2>/dev/null || true
echo "  Note: Remove any 'alias vox=...' lines from your shell config manually."
```

---

### 5.4 No Verification Step After Install

**Severity: P2**

After installation succeeds, the script immediately prints "Ready! Try it:" and shows usage examples. It does not verify that the `vox` binary is actually on `$PATH` or that it runs successfully.

On some systems (certain Linux distros, or if `~/.local/bin` is not in `PATH`), `pip --user` installs the binary to a location not in `$PATH`. The user sees "Ready!" but then gets `command not found: vox`.

**Suggested fix:** After install, run a verification step:
```bash
if command -v vox &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} vox is on PATH"
else
    echo -e "  ${YELLOW}!${NC} vox is installed but not on PATH"
    echo -e "  ${DIM}  Add to your shell config: export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi
```

---

## 6. Missing UX Features for a Real Product

### 6.1 No Onboarding / Tutorial Mode

**Severity: P1**

There is no "try it out" onboarding. A user's first experience is a blank `vox >` prompt. A guided first-run (e.g., 3-step interactive walkthrough) dramatically improves activation rates for CLI tools.

**Suggested implementation:**

```
Welcome to vox! Let me show you how it works.
  → Try: "list all files in current folder"
```

Then after a few successful translations, the onboarding completes and does not show again (gated by `~/.config/vox/onboarded`).

---

### 6.2 No "Did You Mean?" for Near-Misses

**Severity: P2**

When the model produces a syntactically valid but semantically wrong command, or when it fails entirely, vox has no recovery path. Competitors like `gh` and `git` use Levenshtein distance on command names to suggest alternatives. For NL queries, a simpler version would be: if translation fails, re-run with a higher temperature and offer up to 3 alternative commands.

---

### 6.3 No Favorites / Saved Aliases

**Severity: P3**

A power user will repeatedly use vox for the same patterns. There is no way to save a translation as a named alias or mark it as a favorite. A `~/.config/vox/favorites.toml` with a `vox save` command would enable:
```
vox > kill everything on port 8080
  lsof -ti:8080 | xargs kill
  Run it? [Y/n/c/s]  s = save as alias
  Alias name: killport
  → Saved. Run with: vox :killport
```

---

### 6.4 No Opt-In Usage Analytics / Telemetry

**Severity: P3**

For improving the fine-tuned model (which is the core differentiator of vox over generic NL-to-shell tools), anonymous telemetry of query patterns would be invaluable training signal. There is no infrastructure for this.

**Suggested approach:** Opt-in during first run ("Help improve vox's model? Share anonymous translations? [y/N]"), storing accepted pairs to `~/.config/vox/feedback.jsonl` with a periodic upload command (`vox feedback upload`).

---

### 6.5 No Configuration File — Only Environment Variables

**Severity: P2**

Vox configuration is entirely via environment variables (`VOX_MODEL`, `VOX_API_URL`). This means persistent configuration requires the user to edit their shell profile. A `~/.config/vox/config.toml` with sensible defaults would be more discoverable.

**Suggested format:**
```toml
[model]
name = "nl2shell"
api_url = "http://localhost:11434"

[behavior]
auto_execute = false
dangerous_confirm = true
```

---

### 6.6 No Multi-Line Command Handling

**Severity: P2**

Multi-line commands (pipelines spanning multiple lines, here-docs) are out of scope for the current approach, but single-line pipelines that are very long have no visual wrapping or indication. The `num_predict = 256` token cap in `engine.py` also silently truncates long generated commands, which would produce syntactically broken output.

**Suggested fix:** Detect truncated output (commands ending mid-pipe, unclosed quotes) and show a warning rather than presenting a broken command for execution.

---

### 6.7 No `vox --version` in REPL Header

**Severity: P3**

The REPL header shows `vox v0.1.0 — talk to your terminal` which is correct. But the version is defined in `src/vox/__init__.py` as a hardcoded string `__version__ = "0.1.0"` with no automated sync to `pyproject.toml`. This is a maintenance hazard: version bumps require editing two files.

**Suggested fix:** Use `importlib.metadata` to read the version at runtime:
```python
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("vox-shell")
except PackageNotFoundError:
    __version__ = "dev"
```

---

## 7. Summary: Priority Action Items

| Priority | Issue | File |
|----------|-------|------|
| P0 | Default model `nl2shell` unavailable on Ollama registry | `engine.py`, README |
| P1 | No thinking/progress spinner during translation | `cli.py` |
| P1 | No in-REPL `!help` or `?` command | `cli.py` |
| P1 | No command history (arrow keys) | `cli.py` |
| P1 | Dangerous command detection absent | `cli.py`, `engine.py` |
| P1 | Ollama error messages undifferentiated (not installed vs not running) | `engine.py`, `cli.py` |
| P1 | No first-run onboarding | `cli.py` |
| P1 | Install: no PATH verification step | `install.sh` |
| P1 | Install: PyPI package not published (no clean fallback) | — |
| P2 | Error rendering inconsistency (Rich vs bare stderr) | `engine.py` |
| P2 | `!` pass-through has no visual echo or exit-code feedback | `cli.py` |
| P2 | No "explain" option (`e`) at the `[Y/n/c]` prompt | `cli.py` |
| P2 | "Could not translate" message too terse | `cli.py` |
| P2 | No in-REPL model switching (`!model <name>`) | `cli.py` |
| P2 | No configuration file (`~/.config/vox/config.toml`) | new file |
| P2 | Install: `2>/dev/null` suppresses real errors | `install.sh` |
| P2 | Uninstall does not clean config directory | `uninstall.sh` |
| P2 | No undo/rephrasing path after failed execution | `cli.py` |
| P3 | No tab completion | `cli.py` |
| P3 | No favorites / aliases | new feature |
| P3 | Version not sourced from `pyproject.toml` dynamically | `__init__.py` |
| P3 | No opt-in analytics for model improvement | new feature |

---

## 8. Quick Wins (Can Ship in One Session)

These are low-effort, high-impact fixes that can be implemented in under 2 hours:

1. **Add thinking spinner** — 3 lines of code wrapping the `translate()` call with `console.status()`
2. **Add `?`/`help` built-in in REPL** — 10 lines in `cli.py`
3. **Add dangerous command warning** — 15-line `is_dangerous()` function + 3 lines in `handle_command()`
4. **Fix error rendering** — pass Rich `Console` into `engine.py` instead of bare `print()`
5. **Add `!` echo** — 1 line before `execute_command()` in the raw pass-through branch
6. **Add PATH check in `install.sh`** — 5 lines at the end of the install script
7. **Fix `__version__` to use `importlib.metadata`** — 5 lines in `__init__.py`

---

*End of report. Total issues identified: 6 P0/P1, 10 P2, 4 P3.*
