"""Command execution and clipboard utilities."""

from __future__ import annotations

import shlex
import subprocess
import sys

from rich.console import Console

console = Console()


def execute_command(cmd: str) -> int:
    """Execute a shell command, returning the exit code."""
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
    """Copy text to the system clipboard. Returns True on success."""
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
