"""Vox CLI — interactive REPL and single-command mode."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

from vox import __version__
from vox.engine import check_ollama, translate

console = Console()

# Patterns that indicate a potentially dangerous command — force confirmation even with --execute
DANGEROUS_PATTERNS = [
    r"\brm\s+.*-\w*[rf]\w*",  # rm -rf, rm -fr, rm -r, rm -f
    r"\brm\s+-\w*R",  # rm -R
    r"\bsudo\b",  # privilege escalation
    r"\bdd\b\s+if=",  # dd disk operations
    r"\bmkfs\b",  # format filesystem
    r"\bshred\b",  # secure delete
    r"\bwipefs\b",  # wipe filesystem
    r"\b:\(\)\s*\{",  # fork bomb
    r"\bchmod\s+777\b",  # world-writable
    r">\s*/dev/sd[a-z]",  # write to raw disk
    r"\bsystemctl\s+(stop|disable|mask)\b",  # stopping services
    r"\bkillall\b",  # kill all processes
    r"\breboot\b",  # reboot
    r"\bshutdown\b",  # shutdown
    r"\bpoweroff\b",  # power off
]

# Patterns that suggest the response is NOT a shell command
NON_SHELL_PATTERNS = [
    r"^\s*import\s+",  # Python import
    r"^\s*from\s+\w+\s+import\b",  # Python from-import
    r"^\s*def\s+\w+\(",  # Python function def
    r"^\s*class\s+\w+",  # Python class
    r"^\s*<\?php",  # PHP
    r"^\s*<html",  # HTML
    r"^\s*\{\"",  # JSON object
]


def is_dangerous(cmd: str) -> bool:
    """Check if a command matches known dangerous patterns."""
    return any(re.search(p, cmd, re.IGNORECASE) for p in DANGEROUS_PATTERNS)


def looks_like_shell(cmd: str) -> bool:
    """Check that the response looks like a shell command, not code in another language."""
    first_line = cmd.split("\n")[0] if cmd else ""
    return not any(re.search(p, first_line) for p in NON_SHELL_PATTERNS)


def print_command(cmd: str, dangerous: bool = False) -> None:
    """Print the translated command with syntax highlighting."""
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
    """Execute a shell command and return its exit code."""
    needs_shell = any(c in cmd for c in "|;&$`()<>")
    try:
        if needs_shell:
            result = subprocess.run(cmd, shell=True, check=False)
        else:
            result = subprocess.run(shlex.split(cmd), check=False)
        return result.returncode
    except ValueError:
        # shlex.split failed — fall back to shell
        result = subprocess.run(cmd, shell=True, check=False)
        return result.returncode
    except FileNotFoundError:
        console.print(f"  [red]Command not found: {cmd.split()[0]}[/red]")
        return 127
    except KeyboardInterrupt:
        console.print("\n[dim][interrupted][/dim]")
        return 130


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard."""
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
    """Prompt user for action: run, copy, or skip."""
    try:
        choice = console.input("  [dim]Run it?[/dim] [bold]\\[Y/n/c][/bold] ").strip().lower()
        if choice in ("", "y", "yes"):
            return "run"
        if choice in ("c", "copy"):
            return "copy"
        return "skip"
    except (KeyboardInterrupt, EOFError):
        return "skip"


def handle_command(query: str, auto_execute: bool = False) -> None:
    """Translate a query and handle the result."""
    # Input length guard
    if len(query) > 1000:
        console.print("  [yellow]Query too long. Try a shorter description.[/yellow]\n")
        return

    try:
        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            cmd = translate(query)
    except KeyboardInterrupt:
        console.print("\n  [dim]Cancelled.[/dim]\n")
        return

    if not cmd:
        console.print("  [red]Could not translate. Try rephrasing.[/red]\n")
        return

    # Reject responses that don't look like shell commands
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


def repl() -> None:
    """Interactive REPL mode."""
    console.print(
        Text.assemble(
            ("vox", "bold cyan"),
            (f" v{__version__}", "dim"),
            (" — talk to your terminal", ""),
        )
    )
    console.print("[dim]Type what you want to do. Ctrl+C to exit.[/dim]")

    if not check_ollama():
        console.print(
            "[yellow]Warning: Ollama not reachable or model not found.[/yellow]\n"
            "[dim]Start Ollama: ollama serve[/dim]\n"
            f"[dim]Pull model:   ollama pull {os.environ.get('VOX_MODEL', 'nl2shell')}[/dim]"
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

        # Special commands
        if query in ("exit", "quit", ":q"):
            console.print("[dim]bye.[/dim]")
            break

        if query == "!help":
            console.print("[dim]  !<cmd>  — run a raw shell command[/dim]")
            console.print("[dim]  exit    — quit the REPL[/dim]")
            console.print()
            continue

        if query.startswith("!"):
            # Raw command pass-through — show what will run
            raw_cmd = query[1:].strip()
            if raw_cmd:
                console.print(f"  [dim]$ {raw_cmd}[/dim]")
                execute_command(raw_cmd)
            console.print()
            continue

        try:
            handle_command(query)
        except KeyboardInterrupt:
            console.print("\n  [dim]Cancelled.[/dim]\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vox",
        description="Talk to your terminal. Natural language to shell commands.",
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Natural language command (omit for interactive REPL mode)",
    )
    parser.add_argument("--version", action="version", version=f"vox {__version__}")
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Ollama model name (default: nl2shell)",
    )
    parser.add_argument(
        "--execute",
        "-x",
        action="store_true",
        help="Auto-execute safe commands (dangerous commands still require confirmation)",
    )
    parser.add_argument(
        "--api",
        default=None,
        help="Ollama API URL (default: http://localhost:11434)",
    )

    args = parser.parse_args()

    if args.model:
        os.environ["VOX_MODEL"] = args.model
    if args.api:
        os.environ["VOX_API_URL"] = args.api

    if not args.query:
        repl()
    else:
        query = " ".join(args.query)
        handle_command(query, auto_execute=args.execute)


if __name__ == "__main__":
    main()
