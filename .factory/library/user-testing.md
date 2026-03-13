# User Testing

Testing surface, validation tools, and resource cost classification.

**What belongs here:** How to test user-facing behavior, what tools to use, resource constraints.

---

## Validation Surface

- **CLI commands** (non-interactive): `vox --version`, `vox config show`, `vox config path`, `vox agent --list`
- **CLI with Ollama** (requires running Ollama): `vox "list files"` (NL-to-shell translation)
- **REPL** (interactive): Cannot be tested non-interactively. Validate via unit tests only.
- **Agent delegation**: Requires agent binaries in PATH. Can test `vox agent --list` non-interactively.

## Validation Tools

- Primary: shell commands via Execute tool
- Tests: `uv run pytest tests/ -v`
- Lint: `uv run ruff check src/`
- REPL testing: unit tests with mocked input only (no tuistory needed for this scope)

## Validation Concurrency

- Machine: 24GB RAM, 12 CPU cores
- Test suite: 27 tests in 0.04s (extremely lightweight)
- CLI validation: no heavy services to start (Ollama already running)
- Max concurrent validators: **5** (each pytest/CLI invocation is trivial, ~50MB overhead)
