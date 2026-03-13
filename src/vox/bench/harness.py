"""Terminal-Bench 2.0 harness — task definitions, runner, and scorer.

Each Task has:
  - description: plain-English description of what to accomplish
  - verify_cmd: shell command that exits 0 if the task succeeded, non-zero otherwise
  - solution: reference human-written solution (used only for documentation)
  - category: task category (file, process, git, network, package, …)
  - timeout: seconds to allow for agent + execution

Usage::

    from vox.bench.harness import Harness
    from vox.bench.tasks import BUILTIN_TASKS
    from vox.config import VoxConfig

    harness = Harness(VoxConfig())
    results = harness.run_all(BUILTIN_TASKS)
    harness.print_summary(results)
"""

from __future__ import annotations

import contextlib
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from vox.config import VoxConfig

console = Console()


@dataclass
class Task:
    """A single Terminal-Bench task."""

    id: str
    description: str
    verify_cmd: str
    solution: str = ""
    category: str = "general"
    timeout: int = 30
    setup_cmd: str = ""
    teardown_cmd: str = ""


@dataclass
class BenchResult:
    """Result of running a single benchmark task."""

    task_id: str
    description: str
    category: str
    passed: bool
    generated_cmd: str = ""
    exit_code: int = -1
    verify_exit_code: int = -1
    elapsed_s: float = 0.0
    error: str = ""


@dataclass
class Harness:
    """Run Terminal-Bench tasks using the Vox translation engine."""

    cfg: VoxConfig
    dry_run: bool = False
    results: list[BenchResult] = field(default_factory=list)

    def _setup(self, task: Task) -> None:
        if task.setup_cmd:
            subprocess.run(task.setup_cmd, shell=True, check=False, timeout=30)

    def _teardown(self, task: Task) -> None:
        if task.teardown_cmd:
            subprocess.run(task.teardown_cmd, shell=True, check=False, timeout=30)

    def run_task(self, task: Task) -> BenchResult:
        """Translate, execute, then verify a single task. Returns a BenchResult."""
        from vox.engine import translate

        start = time.monotonic()

        try:
            self._setup(task)
        except Exception as exc:
            return BenchResult(
                task_id=task.id,
                description=task.description,
                category=task.category,
                passed=False,
                error=f"setup failed: {exc}",
                elapsed_s=time.monotonic() - start,
            )

        cmd = ""
        exit_code = -1
        verify_exit_code = -1
        error = ""

        try:
            cmd = translate(task.description, self.cfg) or ""
            if not cmd:
                error = "translation returned empty command"
            elif not self.dry_run:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    check=False,
                    timeout=task.timeout,
                    capture_output=True,
                    text=True,
                )
                exit_code = result.returncode
        except subprocess.TimeoutExpired:
            error = f"command timed out after {task.timeout}s"
            exit_code = 124
        except Exception as exc:
            error = str(exc)

        if not error and not self.dry_run and task.verify_cmd:
            try:
                vr = subprocess.run(
                    task.verify_cmd,
                    shell=True,
                    check=False,
                    timeout=task.timeout,
                    capture_output=True,
                    text=True,
                )
                verify_exit_code = vr.returncode
            except subprocess.TimeoutExpired:
                error = f"verify timed out after {task.timeout}s"
                verify_exit_code = 124
            except Exception as exc:
                error = str(exc)

        passed = (
            not error
            and not self.dry_run
            and verify_exit_code == 0
        )

        elapsed = time.monotonic() - start

        with contextlib.suppress(Exception):
            self._teardown(task)

        return BenchResult(
            task_id=task.id,
            description=task.description,
            category=task.category,
            passed=passed,
            generated_cmd=cmd,
            exit_code=exit_code,
            verify_exit_code=verify_exit_code,
            elapsed_s=elapsed,
            error=error,
        )

    def run_all(self, tasks: list[Task]) -> list[BenchResult]:
        """Run all tasks and return results."""
        results: list[BenchResult] = []
        for task in tasks:
            with console.status(f"[dim]Running {task.id}: {task.description[:60]}…[/dim]"):
                result = self.run_task(task)
            icon = "[green]✓[/green]" if result.passed else "[red]✗[/red]"
            console.print(f"  {icon} [{result.category}] {task.id}: {task.description[:60]}")
            if result.error:
                console.print(f"      [dim red]{result.error}[/dim red]")
            results.append(result)
        self.results = results
        return results

    def print_summary(self, results: list[BenchResult] | None = None) -> None:
        """Print a rich summary table of all results."""
        if results is None:
            results = self.results

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        score = (passed / total * 100) if total else 0.0

        table = Table(title="Terminal-Bench Results", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=20)
        table.add_column("Category", width=12)
        table.add_column("Description", width=50)
        table.add_column("Pass", justify="center", width=6)
        table.add_column("Time(s)", justify="right", width=8)

        for r in results:
            status = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
            table.add_row(
                r.task_id,
                r.category,
                r.description[:48],
                status,
                f"{r.elapsed_s:.1f}",
            )

        console.print(table)
        console.print(
            f"\n[bold]Score: {passed}/{total} ({score:.1f}%)[/bold]  "
            f"— [dim]avg {sum(r.elapsed_s for r in results) / total:.1f}s/task[/dim]"
            if total
            else "\n[bold]No tasks run.[/bold]"
        )
