"""Vox CLI — subcommand dispatcher with interactive REPL, voice, and agent modes."""

from __future__ import annotations

import argparse
import atexit
import os
import readline
import sys
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

from vox import __version__
from vox.config import CONFIG_FILE, VoxConfig, init_config, load_config
from vox.executor import copy_to_clipboard, execute_command
from vox.safety import is_dangerous, looks_like_shell

# Re-export for backward compatibility (tests import these from vox.cli)
__all__ = [
    "copy_to_clipboard",
    "execute_command",
    "is_dangerous",
    "looks_like_shell",
]

HISTORY_FILE = Path.home() / ".vox_history"


def setup_history() -> None:
    """Load command history and register save-on-exit."""
    try:
        if HISTORY_FILE.exists():
            readline.read_history_file(HISTORY_FILE)
        readline.set_history_length(1000)
        atexit.register(readline.write_history_file, str(HISTORY_FILE))
    except OSError:
        pass


console = Console()


def print_command(cmd: str, dangerous: bool = False) -> None:
    console.print()
    syntax = Syntax(cmd, "bash", theme="monokai", line_numbers=False, padding=1)
    console.print(syntax)
    if dangerous:
        console.print(
            "  [bold red]Warning: this command looks destructive. Review carefully.[/bold red]"
        )
    if "\n" in cmd:
        console.print("  [yellow]Note: multi-line command.[/yellow]")


def _get_knowledge(cfg: VoxConfig):
    """Get the knowledge store singleton (lazy init)."""
    if not cfg.learning.enabled:
        return None
    from pathlib import Path

    from vox.knowledge import KnowledgeStore

    db_path = Path(cfg.learning.db_path) if cfg.learning.db_path else None
    return KnowledgeStore(db_path=db_path)


def prompt_action(cmd: str) -> str:
    try:
        choice = console.input("  [dim]Run it?[/dim] [bold]\\[Y/n/c/e][/bold] ").strip().lower()
        if choice in ("", "y", "yes"):
            return "run"
        if choice in ("c", "copy"):
            return "copy"
        if choice in ("e", "edit"):
            return "edit"
        return "skip"
    except (KeyboardInterrupt, EOFError):
        return "skip"


def handle_command(query: str, cfg: VoxConfig, auto_execute: bool = False) -> None:
    if len(query) > 1000:
        console.print("  [yellow]Query too long. Try a shorter description.[/yellow]\n")
        return

    knowledge = _get_knowledge(cfg)
    cwd = os.getcwd()
    from_cache = False

    # Check learned patterns first (skip LLM if high-confidence match)
    if knowledge and cfg.learning.auto_learn:
        matches = knowledge.find_pattern(query, cwd=cwd)
        if matches:
            top = matches[0]
            if top.confidence >= cfg.learning.min_confidence and top.success_count >= cfg.learning.min_success_count:
                cmd = top.command
                from_cache = True

    if not from_cache:
        from vox.engine import translate

        try:
            with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                cmd = translate(query, cfg, knowledge=knowledge, cwd=cwd)
        except KeyboardInterrupt:
            console.print("\n  [dim]Cancelled.[/dim]\n")
            return

    if not cmd:
        console.print("  [red]Could not translate. Try rephrasing.[/red]\n")
        return

    if not looks_like_shell(cmd):
        console.print("  [red]Response didn't look like a shell command. Try rephrasing.[/red]\n")
        return

    dangerous = is_dangerous(cmd)
    if from_cache:
        console.print("\n  [dim cyan][learned][/dim cyan]")
    print_command(cmd, dangerous=dangerous)

    if auto_execute and not dangerous:
        rc = execute_command(cmd)
        if rc != 0:
            console.print(f"  [dim]exit {rc}[/dim]")
        else:
            _learn_success(knowledge, query, cmd, cwd)
        console.print()
        return

    if auto_execute and dangerous:
        console.print(
            "  [bold yellow]Dangerous command detected — manual confirmation required.[/bold yellow]"
        )

    action = prompt_action(cmd)
    if action == "run":
        console.print()
        rc = execute_command(cmd)
        if rc != 0:
            console.print(f"  [dim]exit {rc}[/dim]")
            _learn_error(knowledge, cmd, cwd)
        else:
            _learn_success(knowledge, query, cmd, cwd)
        console.print()
    elif action == "edit":
        try:
            corrected = console.input("  [dim]Correct command:[/dim] ").strip()
        except (KeyboardInterrupt, EOFError):
            corrected = ""
        if corrected:
            if knowledge:
                knowledge.save_correction(query, cmd, corrected)
                console.print("  [green]Saved correction.[/green]")
            print_command(corrected, dangerous=is_dangerous(corrected))
            action2 = prompt_action(corrected)
            if action2 == "run":
                console.print()
                execute_command(corrected)
                console.print()
        else:
            console.print()
    elif action == "copy":
        if copy_to_clipboard(cmd):
            console.print("  [green]Copied to clipboard.[/green]\n")
        else:
            console.print(f"  [dim]{cmd}[/dim]\n")
    else:
        console.print()


def _learn_success(knowledge, query: str, cmd: str, cwd: str) -> None:
    """Save a successful command to the knowledge store."""
    if knowledge:
        import sys

        os_name = "macOS" if sys.platform == "darwin" else "Linux"
        knowledge.save_pattern(query, cmd, cwd, os_name)


def _learn_error(knowledge, cmd: str, cwd: str) -> None:
    """Save a failed command to the knowledge store."""
    if knowledge:
        knowledge.save_error(cmd, "", cwd)


# ── REPL ─────────────────────────────────────────────────────────────────────


def repl(cfg: VoxConfig) -> None:
    setup_history()

    from vox.engine import check_ollama

    console.print(
        Text.assemble(
            ("vox", "bold cyan"),
            (f" v{__version__}", "dim"),
            (" — talk to your terminal", ""),
        )
    )
    console.print("[dim]Type what you want to do. Ctrl+C to exit.[/dim]")
    console.print("[dim]  !listen — voice  |  !agent <task> — delegate  |  !learn — show patterns[/dim]")

    model = cfg.model.name
    status = check_ollama(cfg)
    if status == "no_ollama":
        console.print(
            "\n[yellow]Ollama is not running.[/yellow]\n"
            "[dim]  Install: https://ollama.ai[/dim]\n"
            "[dim]  Start:   ollama serve[/dim]"
        )
    elif status == "no_model":
        console.print(
            f"\n[yellow]Model '{model}' not found locally.[/yellow]\n"
            f"[dim]  Pull it: ollama pull {model}[/dim]"
        )
    console.print()

    while True:
        try:
            query = console.input("[bold cyan]vox >[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]bye.[/dim]")
            break

        if not query:
            continue

        if query in ("exit", "quit", ":q"):
            console.print("[dim]bye.[/dim]")
            break

        if query == "!help":
            console.print("[dim]  !<cmd>   — run a raw shell command[/dim]")
            console.print("[dim]  !listen  — voice input (requires voice extras)[/dim]")
            console.print("[dim]  !agent   — delegate to an AI agent[/dim]")
            console.print("[dim]  exit     — quit the REPL[/dim]")
            console.print()
            continue

        if query == "!listen":
            _repl_listen(cfg)
            continue

        if query.startswith("!agent "):
            task = query[7:].strip()
            if task:
                _repl_agent(task, cfg)
            continue

        if query.startswith("!"):
            raw_cmd = query[1:].strip()
            if raw_cmd:
                console.print(f"  [dim]$ {raw_cmd}[/dim]")
                execute_command(raw_cmd)
            console.print()
            continue

        try:
            handle_command(query, cfg)
        except KeyboardInterrupt:
            console.print("\n  [dim]Cancelled.[/dim]\n")


def _repl_listen(cfg: VoxConfig) -> None:
    """Handle !listen in the REPL — record and transcribe voice input."""
    try:
        from vox.voice.asr import transcribe_mic
    except ImportError:
        console.print(
            "  [yellow]Voice extras not installed.[/yellow]\n"
            '  [dim]Install with: pip install "vox-shell[voice]"[/dim]\n'
        )
        return

    console.print("  [dim]Listening... (Ctrl+C to stop)[/dim]")
    try:
        text = transcribe_mic(cfg)
    except KeyboardInterrupt:
        console.print("  [dim]Cancelled.[/dim]\n")
        return

    if text:
        console.print(f"  [dim]Heard:[/dim] {text}")
        handle_command(text, cfg)
    else:
        console.print("  [yellow]Could not transcribe audio.[/yellow]\n")


def _repl_agent(task: str, cfg: VoxConfig) -> None:
    """Handle !agent <task> in the REPL."""
    try:
        from vox.agents.router import route_and_run
    except ImportError:
        console.print("  [red]Agent module not available.[/red]\n")
        return

    try:
        with console.status("[dim]Delegating to agent...[/dim]", spinner="dots"):
            result = route_and_run(task, cfg)
        if result:
            console.print(result)
        console.print()
    except KeyboardInterrupt:
        console.print("\n  [dim]Cancelled.[/dim]\n")


# ── Subcommands ──────────────────────────────────────────────────────────────


def cmd_listen(args: argparse.Namespace, cfg: VoxConfig) -> None:
    """Voice input mode — record, transcribe, translate to shell."""
    try:
        from vox.voice.asr import transcribe_mic
    except ImportError:
        console.print(
            "[yellow]Voice extras not installed.[/yellow]\n"
            '[dim]Install with: pip install "vox-shell[voice]"[/dim]'
        )
        sys.exit(1)

    console.print("[dim]Listening... (Ctrl+C to stop)[/dim]")
    try:
        text = transcribe_mic(cfg)
    except KeyboardInterrupt:
        console.print("[dim]Cancelled.[/dim]")
        return

    if not text:
        console.print("[yellow]Could not transcribe audio.[/yellow]")
        return

    console.print(f"[dim]Heard:[/dim] {text}")
    handle_command(text, cfg, auto_execute=args.execute)


def cmd_speak(args: argparse.Namespace, cfg: VoxConfig) -> None:
    """Text-to-speech — speak the given text aloud."""
    try:
        from vox.voice.tts import speak_text
    except ImportError:
        console.print(
            "[yellow]Voice extras not installed.[/yellow]\n"
            '[dim]Install with: pip install "vox-shell[voice]"[/dim]'
        )
        sys.exit(1)

    text = " ".join(args.text) if args.text else None
    if not text:
        console.print("[yellow]No text provided.[/yellow]")
        return

    speak_text(text, cfg)


def cmd_agent(args: argparse.Namespace, cfg: VoxConfig) -> None:
    """Delegate a task to an AI coding agent."""
    from vox.agents.router import discover_agents, route_and_run

    if args.list:
        agents = discover_agents()
        if not agents:
            console.print("[yellow]No agents found in PATH.[/yellow]")
            return
        console.print("[bold]Detected agents:[/bold]")
        for name, path in agents.items():
            console.print(f"  [cyan]{name}[/cyan] — {path}")
        return

    task = " ".join(args.task) if args.task else None
    if not task:
        console.print("[yellow]No task provided. Usage: vox agent 'fix the tests'[/yellow]")
        return

    if args.use:
        os.environ["VOX_PREFERRED_AGENT"] = args.use

    try:
        with console.status("[dim]Delegating to agent...[/dim]", spinner="dots"):
            result = route_and_run(task, cfg)
        if result:
            console.print(result)
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")


def cmd_config(args: argparse.Namespace, _cfg: VoxConfig) -> None:
    """Manage vox configuration."""
    if args.config_action == "init":
        path = init_config()
        console.print(f"[green]Config created at[/green] {path}")
    elif args.config_action == "show":
        if CONFIG_FILE.is_file():
            content = CONFIG_FILE.read_text()
            syntax = Syntax(content, "toml", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print("[yellow]No config file found. Run: vox config init[/yellow]")
    elif args.config_action == "edit":
        if not CONFIG_FILE.is_file():
            init_config()
        editor = os.environ.get("EDITOR", "nano")
        os.execvp(editor, [editor, str(CONFIG_FILE)])
    elif args.config_action == "path":
        console.print(str(CONFIG_FILE))
    else:
        console.print("[dim]Usage: vox config {init|show|edit|path}[/dim]")


def cmd_learn(args: argparse.Namespace, cfg: VoxConfig) -> None:
    """Manage the self-learning knowledge store."""
    knowledge = _get_knowledge(cfg)
    if not knowledge:
        console.print("[yellow]Learning is disabled. Enable in config: [learning] enabled = true[/yellow]")
        return

    action = args.learn_action or "show"

    if action == "show":
        patterns = knowledge.top_patterns(limit=20)
        if not patterns:
            console.print("[dim]No learned patterns yet. Use vox and it will learn over time.[/dim]")
            return
        console.print("[bold]Top learned patterns:[/bold]\n")
        for p in patterns:
            console.print(f"  [cyan]{p['query']}[/cyan] → [green]{p['command']}[/green] [dim]({p['uses']} uses)[/dim]")
    elif action == "stats":
        stats = knowledge.stats()
        console.print("[bold]Knowledge store stats:[/bold]\n")
        for key, val in stats.items():
            console.print(f"  [cyan]{key}[/cyan]: {val}")
    elif action == "clear":
        knowledge.clear()
        console.print("[green]Knowledge store cleared.[/green]")
    elif action == "export":
        data = knowledge.export_json()
        if args.file:
            Path(args.file).write_text(data)
            console.print(f"[green]Exported to {args.file}[/green]")
        else:
            console.print(data)
    elif action == "import":
        if not args.file:
            console.print("[yellow]Usage: vox learn import --file patterns.json[/yellow]")
            return
        data = Path(args.file).read_text()
        count = knowledge.import_json(data)
        console.print(f"[green]Imported {count} patterns.[/green]")


# ── Main entry point ─────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="vox",
        description="Talk to your terminal. Natural language to shell commands.",
    )
    parser.add_argument("--version", action="version", version=f"vox {__version__}")
    parser.add_argument("--config", type=Path, default=None, help="Path to config file")
    parser.add_argument("--model", "-m", default=None, help="Ollama model name")
    parser.add_argument(
        "--execute",
        "-x",
        action="store_true",
        help="Auto-execute safe commands",
    )
    parser.add_argument("--api", default=None, help="Ollama API URL")

    subparsers = parser.add_subparsers(dest="command")

    # ── listen ────────────────────────────────────────────────────────────
    listen_parser = subparsers.add_parser("listen", help="Voice input → shell command")
    listen_parser.add_argument(
        "--execute",
        "-x",
        action="store_true",
        help="Auto-execute safe commands",
    )

    # ── speak ─────────────────────────────────────────────────────────────
    speak_parser = subparsers.add_parser("speak", help="Text-to-speech")
    speak_parser.add_argument("text", nargs="*", help="Text to speak")

    # ── agent ─────────────────────────────────────────────────────────────
    agent_parser = subparsers.add_parser("agent", help="Delegate task to AI agent")
    agent_parser.add_argument("task", nargs="*", help="Task description")
    agent_parser.add_argument("--list", "-l", action="store_true", help="List detected agents")
    agent_parser.add_argument(
        "--use",
        "-u",
        default=None,
        help="Force a specific agent (claude, codex, gemini, amp, droid)",
    )

    # ── config ────────────────────────────────────────────────────────────
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument(
        "config_action",
        nargs="?",
        choices=["init", "show", "edit", "path"],
        default="show",
        help="Config action",
    )

    # ── learn ─────────────────────────────────────────────────────────────
    learn_parser = subparsers.add_parser("learn", help="Manage learned patterns")
    learn_parser.add_argument(
        "learn_action",
        nargs="?",
        choices=["show", "stats", "clear", "export", "import"],
        default="show",
        help="Learning action",
    )
    learn_parser.add_argument("--file", "-f", default=None, help="File path for export/import")

    return parser


_SUBCOMMANDS = frozenset({"listen", "speak", "agent", "config", "learn"})


def main() -> None:
    parser = _build_parser()

    # Detect whether the first positional arg is a known subcommand.
    # If not, strip positionals out so argparse only sees flags, then
    # treat the stripped positionals as a free-form query.
    raw = sys.argv[1:]
    flags: list[str] = []
    query_words: list[str] = []
    has_subcommand = False

    # Scan for the first non-flag token to decide dispatch mode
    for token in raw:
        if token.startswith("-"):
            break
        if token in _SUBCOMMANDS:
            has_subcommand = True
        break

    if has_subcommand:
        args = parser.parse_args()
        query_words = []
    else:
        # Separate flags from positional query words
        skip_next = False
        for token in raw:
            if skip_next:
                flags.append(token)
                skip_next = False
            elif token.startswith("-"):
                flags.append(token)
                # Flags that consume a value
                if token in ("--model", "-m", "--api", "--config"):
                    skip_next = True
            else:
                query_words.append(token)
        args = parser.parse_args(flags)

    args.query = query_words

    cfg = load_config(args.config)

    # CLI flag overrides
    if hasattr(args, "model") and args.model:
        cfg.model.name = args.model
    if hasattr(args, "api") and args.api:
        cfg.model.api_url = args.api

    # Dispatch subcommands
    if args.command == "listen":
        cmd_listen(args, cfg)
    elif args.command == "speak":
        cmd_speak(args, cfg)
    elif args.command == "agent":
        cmd_agent(args, cfg)
    elif args.command == "config":
        cmd_config(args, cfg)
    elif args.command == "learn":
        cmd_learn(args, cfg)
    elif args.query:
        query = " ".join(args.query)
        handle_command(query, cfg, auto_execute=args.execute)
    else:
        repl(cfg)


if __name__ == "__main__":
    main()
