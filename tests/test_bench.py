"""Tests for the Terminal-Bench 2.0 harness."""

from unittest.mock import MagicMock, patch

from vox.bench.harness import BenchResult, Harness, Task
from vox.bench.tasks import BUILTIN_TASKS
from vox.config import VoxConfig

# ── Task dataclass ────────────────────────────────────────────────────────────


def test_task_defaults():
    t = Task(id="t1", description="list files", verify_cmd="true")
    assert t.category == "general"
    assert t.timeout == 30
    assert t.setup_cmd == ""
    assert t.teardown_cmd == ""
    assert t.solution == ""


def test_task_custom_fields():
    t = Task(
        id="t2",
        description="check space",
        verify_cmd="df -h",
        category="system",
        timeout=60,
        solution="df -h",
    )
    assert t.category == "system"
    assert t.timeout == 60


# ── BenchResult dataclass ─────────────────────────────────────────────────────


def test_bench_result_defaults():
    r = BenchResult(task_id="t1", description="list files", category="file", passed=True)
    assert r.passed is True
    assert r.generated_cmd == ""
    assert r.error == ""
    assert r.exit_code == -1


# ── BUILTIN_TASKS ─────────────────────────────────────────────────────────────


def test_builtin_tasks_not_empty():
    assert len(BUILTIN_TASKS) > 0


def test_builtin_tasks_have_required_fields():
    for task in BUILTIN_TASKS:
        assert task.id, f"task missing id: {task}"
        assert task.description, f"task {task.id} missing description"
        assert task.verify_cmd is not None, f"task {task.id} missing verify_cmd"
        assert task.category, f"task {task.id} missing category"


def test_builtin_task_ids_are_unique():
    ids = [t.id for t in BUILTIN_TASKS]
    assert len(ids) == len(set(ids)), "Duplicate task IDs found"


def test_builtin_tasks_categories():
    categories = {t.category for t in BUILTIN_TASKS}
    assert "file" in categories
    assert "text" in categories
    assert "process" in categories
    assert "system" in categories


# ── Harness.run_task ──────────────────────────────────────────────────────────


@patch("vox.bench.harness.subprocess.run")
@patch("vox.engine.httpx.post")
def test_run_task_pass(mock_post, mock_run):
    """Task passes when translate returns a command and verify exits 0."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": "ls -la"}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    task = Task(id="t1", description="list files", verify_cmd="true")
    harness = Harness(cfg=VoxConfig())
    result = harness.run_task(task)

    assert result.task_id == "t1"
    assert result.generated_cmd == "ls -la"
    assert result.passed is True


@patch("vox.bench.harness.subprocess.run")
@patch("vox.engine.httpx.post")
def test_run_task_fail_verify(mock_post, mock_run):
    """Task fails when verify command returns non-zero."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": "ls -la"}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # exec returns 0, verify returns 1
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=1, stdout="", stderr="failed"),
    ]

    task = Task(id="t1", description="list files", verify_cmd="false")
    harness = Harness(cfg=VoxConfig())
    result = harness.run_task(task)

    assert result.passed is False
    assert result.verify_exit_code == 1


@patch("vox.engine.httpx.post")
def test_run_task_empty_translation(mock_post):
    """Task fails gracefully when translation returns empty."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": ""}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    task = Task(id="t1", description="list files", verify_cmd="true")
    harness = Harness(cfg=VoxConfig())
    result = harness.run_task(task)

    assert result.passed is False
    assert "empty" in result.error


@patch("vox.engine.httpx.post")
def test_run_task_dry_run(mock_post):
    """In dry_run mode, commands are translated but never executed."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": "ls -la"}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    task = Task(id="t1", description="list files", verify_cmd="true")
    harness = Harness(cfg=VoxConfig(), dry_run=True)

    with patch("vox.bench.harness.subprocess.run") as mock_run:
        result = harness.run_task(task)
        mock_run.assert_not_called()

    assert result.generated_cmd == "ls -la"
    assert result.passed is False  # dry_run never marks passed


@patch("vox.engine.httpx.post", side_effect=Exception("connection error"))
def test_run_task_translation_error(mock_post):
    """Task records error when translation raises an exception."""
    task = Task(id="t1", description="list files", verify_cmd="true")
    harness = Harness(cfg=VoxConfig())
    result = harness.run_task(task)
    assert result.passed is False


# ── Harness.run_all ───────────────────────────────────────────────────────────


@patch("vox.bench.harness.subprocess.run")
@patch("vox.engine.httpx.post")
def test_run_all_returns_all_results(mock_post, mock_run):
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": "true"}}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    tasks = [
        Task(id="t1", description="task one", verify_cmd="true"),
        Task(id="t2", description="task two", verify_cmd="true"),
    ]
    harness = Harness(cfg=VoxConfig())
    results = harness.run_all(tasks)

    assert len(results) == 2
    assert {r.task_id for r in results} == {"t1", "t2"}


# ── Harness.print_summary ─────────────────────────────────────────────────────


def test_print_summary_no_tasks(capsys):
    harness = Harness(cfg=VoxConfig())
    harness.print_summary([])


def test_print_summary_mixed_results():
    results = [
        BenchResult(task_id="t1", description="pass task", category="file", passed=True),
        BenchResult(task_id="t2", description="fail task", category="text", passed=False),
    ]
    harness = Harness(cfg=VoxConfig())
    harness.print_summary(results)


# ── Pi agent registration ─────────────────────────────────────────────────────


def test_pi_agent_registered():
    from vox.agents.router import ALL_AGENTS

    names = {a.name for a in ALL_AGENTS}
    assert "pi" in names


@patch("shutil.which")
def test_pi_agent_discover(mock_which):
    from vox.agents.router import discover_agents

    def side_effect(binary):
        return "/usr/local/bin/pi" if binary == "pi" else None

    mock_which.side_effect = side_effect
    agents = discover_agents()
    assert "pi" in agents
    assert agents["pi"] == "/usr/local/bin/pi"


@patch("vox.agents.base.BaseAgent._exec")
def test_pi_agent_run(mock_exec):
    from vox.agents.base import AgentResult
    from vox.agents.pi import PiAgent

    mock_exec.return_value = AgentResult(agent="pi", output="done", exit_code=0)
    result = PiAgent.run("fix the bug")
    assert result.agent == "pi"
    cmd = mock_exec.call_args[0][0]
    assert cmd[0] == "pi"
    assert "--print" in cmd
    assert "fix the bug" in cmd
