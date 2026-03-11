"""Vox CLI — interactive REPL and single-command mode."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text

from vox import __version__
from vox.engine import check_ollama, translate

console = Console()


def print_command(cmd: str) -> None:
    """Print the translated command with syntax highlighting."""
    console.print()
    syntax = Syntax(cmd, "bash", theme="monokai", line_numbers=False, padding=1)
    console.print(syntax)


def execute_command(cmd: str) -> int:
    """Execute a shell command and return its exit code."""
    try:
        result = subprocess.run(cmd, shell=True, check=False)
        return result.returncode
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
    cmd = translate(query)
    if not cmd:
        console.print("  [red]Could not translate. Try rephrasing.[/red]\n")
        return

    print_command(cmd)

    if auto_execute:
        rc = execute_command(cmd)
        if rc != 0:
            console.print(f"  [dim]exit {rc}[/dim]")
        console.print()
        return

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

        if query.startswith("!"):
            # Raw command pass-through
            execute_command(query[1:].strip())
            console.print()
            continue

        handle_command(query)


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
        help="Execute the command without asking for confirmation",
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
