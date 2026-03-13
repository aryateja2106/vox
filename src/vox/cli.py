"""Vox CLI — subcommand dispatcher with interactive REPL, voice, and agent modes."""

from __future__ import annotations

import argparse
import atexit
import os
import re
import readline
import shlex
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

from vox import __version__
from vox.config import CONFIG_FILE, VoxConfig, init_config, load_config

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

DANGEROUS_PATTERNS = [
    r"\brm\s+.*-\w*[rf]\w*",
    r"\brm\s+-\w*R",
    r"\bsudo\b",
    r"\bdd\b\s+if=",
    r"\bmkfs\b",
    r"\bshred\b",
    r"\bwipefs\b",
    r"\b:\(\)\s*\{",
    r"\bchmod\s+777\b",
    r">\s*/dev/sd[a-z]",
    r"\bsystemctl\s+(stop|disable|mask)\b",
    r"\bkillall\b",
    r"\breboot\b",
    r"\bshutdown\b",
    r"\bpoweroff\b",
]

NON_SHELL_PATTERNS = [
    r"^\s*import\s+",
    r"^\s*from\s+\w+\s+import\b",
    r"^\s*def\s+\w+\(",
    r"^\s*class\s+\w+",
    r"^\s*<\?php",
    r"^\s*<html",
    r"^\s*\{\"",
]


def is_dangerous(cmd: str) -> bool:
    return any(re.search(p, cmd, re.IGNORECASE) for p in DANGEROUS_PATTERNS)


def looks_like_shell(cmd: str) -> bool:
    first_line = cmd.split("\n")[0] if cmd else ""
    return not any(re.search(p, first_line) for p in NON_SHELL_PATTERNS)


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


def execute_command(cmd: str) -> int:
    needs_shell = any(c in cmd for c in "|;&$`()<>")
    try:
        if needs_shell:
            result = subprocess.run(cmd, shell=True, check=False)
        else:
            result = subprocess.run(shlex.split(cmd), check=False)
        return result.returncode
    except ValueError:
        result = subprocess.run(cmd, shell=True, check=False)
        return result.returncode
    except FileNotFoundError:
        console.print(f"  [red]Command not found: {cmd.split()[0]}[/red]")
        return 127
    except KeyboardInterrupt:
        console.print("\n[dim][interrupted][/dim]")
        return 130


def copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        else:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(),
                check=True,
            )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def prompt_action(cmd: str) -> str:
    try:
        choice = console.input("  [dim]Run it?[/dim] [bold]\\[Y/n/c][/bold] ").strip().lower()
        if choice in ("", "y", "yes"):
            return "run"
        if choice in ("c", "copy"):
            return "copy"
        return "skip"
    except (KeyboardInterrupt, EOFError):
        return "skip"


def handle_command(query: str, cfg: VoxConfig, auto_execute: bool = False) -> None:
    if len(query) > 1000:
        console.print("  [yellow]Query too long. Try a shorter description.[/yellow]\n")
        return

    from vox.engine import translate

    try:
        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            cmd = translate(query, cfg)
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
    print_command(cmd, dangerous=dangerous)

    if auto_execute and not dangerous:
        rc = execute_command(cmd)
        if rc != 0:
            console.print(f"  [dim]exit {rc}[/dim]")
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
        console.print()
    elif action == "copy":
        if copy_to_clipboard(cmd):
            console.print("  [green]Copied to clipboard.[/green]\n")
        else:
            console.print(f"  [dim]{cmd}[/dim]\n")
    else:
        console.print()


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
    console.print(
        "[dim]  !listen — voice input  |  !agent <task> — delegate to agent[/dim]"
    )

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


# ── Main entry point ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vox",
        description="Talk to your terminal. Natural language to shell commands.",
    )
    parser.add_argument("--version", action="version", version=f"vox {__version__}")
    parser.add_argument(
        "--config", type=Path, default=None, help="Path to config file"
    )

    subparsers = parser.add_subparsers(dest="command")

    # ── Default: shell mode (query as positional args) ────────────────────
    parser.add_argument(
        "query", nargs="*", default=[], help="Natural language command (omit for REPL)"
    )
    parser.add_argument(
        "--model", "-m", default=None, help="Ollama model name"
    )
    parser.add_argument(
        "--execute", "-x", action="store_true",
        help="Auto-execute safe commands",
    )
    parser.add_argument(
        "--api", default=None, help="Ollama API URL"
    )

    # ── listen ────────────────────────────────────────────────────────────
    listen_parser = subparsers.add_parser("listen", help="Voice input → shell command")
    listen_parser.add_argument(
        "--execute", "-x", action="store_true",
        help="Auto-execute safe commands",
    )

    # ── speak ─────────────────────────────────────────────────────────────
    speak_parser = subparsers.add_parser("speak", help="Text-to-speech")
    speak_parser.add_argument("text", nargs="*", help="Text to speak")

    # ── agent ─────────────────────────────────────────────────────────────
    agent_parser = subparsers.add_parser("agent", help="Delegate task to AI agent")
    agent_parser.add_argument("task", nargs="*", help="Task description")
    agent_parser.add_argument(
        "--list", "-l", action="store_true", help="List detected agents"
    )
    agent_parser.add_argument(
        "--use", "-u", default=None, help="Force a specific agent (claude, codex, gemini, amp, droid)"
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

    args = parser.parse_args()
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
    elif args.query:
        query = " ".join(args.query)
        handle_command(query, cfg, auto_execute=args.execute)
    else:
        repl(cfg)


if __name__ == "__main__":
    main()
