# Architecture

Architectural decisions and patterns for Vox.

**What belongs here:** Module structure, design patterns, abstraction decisions.
**What does NOT belong here:** Service ports/commands (use `.factory/services.yaml`).

---

## Module Structure

```
src/vox/
  __init__.py          # __version__ = "0.3.0"
  __main__.py          # Entry: from vox.cli import main; main()
  cli.py               # Argparse subcommand dispatcher, REPL, Rich UI, safety checks
  config.py            # TOML config with dataclass sections, env var overrides
  engine.py            # NL-to-shell translation via Ollama, to be refactored with provider abstraction
  agents/
    __init__.py
    base.py            # BaseAgent ABC, AgentResult dataclass, _exec subprocess runner
    router.py          # Agent routing (currently LLM-based, adding heuristic keyword primary path)
    claude.py, codex.py, gemini.py, amp.py, droid.py  # Headless CLI wrappers
  voice/               # Phase 2, out of scope
```

## Patterns

- **Dataclasses for config:** ModelConfig, VoiceConfig, AgentsConfig, UIConfig → VoxConfig
- **Class-level methods for agents:** All agent methods are @classmethod (no instance state)
- **Rich console for output:** All user-facing output goes through rich.console.Console
- **Safety patterns:** DANGEROUS_PATTERNS (regex list), NON_SHELL_PATTERNS (regex list)
- **Import guards:** Voice modules use try/except ImportError for optional deps
