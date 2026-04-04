"""Tests for CLI subcommand dispatch, flag overrides, safety detection, config actions, and agent behaviors."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vox.cli import (
    cmd_agent,
    cmd_config,
    handle_command,
    is_dangerous,
    looks_like_shell,
    main,
)
from vox.config import VoxConfig

# ── Dispatch tests (VAL-CLI-001 through VAL-CLI-007) ────────────────────────


@patch("vox.cli.repl")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_no_args_launches_repl(mock_load, mock_repl):
    """VAL-CLI-001: No arguments launches REPL."""
    with patch("sys.argv", ["vox"]):
        main()
    mock_repl.assert_called_once()


@patch("vox.cli.handle_command")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_positional_query_dispatches_single_shot(mock_load, mock_handle):
    """VAL-CLI-002: Positional query dispatches single-shot."""
    with patch("sys.argv", ["vox", "find large files"]):
        main()
    mock_handle.assert_called_once()
    call_args = mock_handle.call_args
    assert call_args[0][0] == "find large files"


def test_version_flag(capsys):
    """VAL-CLI-003: --version prints version and exits."""
    with patch("sys.argv", ["vox", "--version"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "0.3.0" in captured.out


@patch("vox.cli.cmd_listen")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_listen_subcommand_dispatches(mock_load, mock_cmd):
    """VAL-CLI-004: listen subcommand dispatches to cmd_listen."""
    with patch("sys.argv", ["vox", "listen"]):
        main()
    mock_cmd.assert_called_once()


@patch("vox.cli.cmd_speak")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_speak_subcommand_dispatches(mock_load, mock_cmd):
    """VAL-CLI-005: speak subcommand dispatches to cmd_speak."""
    with patch("sys.argv", ["vox", "speak", "hello"]):
        main()
    mock_cmd.assert_called_once()


@patch("vox.cli.cmd_agent")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_agent_subcommand_dispatches(mock_load, mock_cmd):
    """VAL-CLI-006: agent subcommand dispatches to cmd_agent."""
    with patch("sys.argv", ["vox", "agent", "fix tests"]):
        main()
    mock_cmd.assert_called_once()


@patch("vox.cli.cmd_config")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_config_subcommand_dispatches(mock_load, mock_cmd):
    """VAL-CLI-007: config subcommand dispatches to cmd_config."""
    with patch("sys.argv", ["vox", "config", "show"]):
        main()
    mock_cmd.assert_called_once()


# ── Flag override tests (VAL-CLI-008 through VAL-CLI-010) ────────────────────


@patch("vox.cli.handle_command")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_model_flag_overrides_config(mock_load, mock_handle):
    """VAL-CLI-008: --model flag overrides config model name."""
    with patch("sys.argv", ["vox", "-m", "custom-model", "query"]):
        main()
    mock_handle.assert_called_once()
    cfg = mock_handle.call_args[0][1]
    assert cfg.model.name == "custom-model"


@patch("vox.cli.handle_command")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_api_flag_overrides_config(mock_load, mock_handle):
    """VAL-CLI-009: --api flag overrides config api_url."""
    with patch("sys.argv", ["vox", "--api", "http://custom:1234", "query"]):
        main()
    mock_handle.assert_called_once()
    cfg = mock_handle.call_args[0][1]
    assert cfg.model.api_url == "http://custom:1234"


@patch("vox.cli.handle_command")
@patch("vox.cli.load_config", return_value=VoxConfig())
def test_execute_flag_enables_auto_execute(mock_load, mock_handle):
    """VAL-CLI-010: -x flag passes auto_execute=True."""
    with patch("sys.argv", ["vox", "-x", "query"]):
        main()
    mock_handle.assert_called_once()
    # auto_execute is passed as keyword argument
    call_kwargs = mock_handle.call_args
    assert call_kwargs[1].get("auto_execute") is True or (
        len(call_kwargs[0]) >= 3 and call_kwargs[0][2] is True
    )


# ── Safety detection tests (VAL-CLI-011, VAL-CLI-012) ────────────────────────


class TestIsDangerous:
    """VAL-CLI-011: Dangerous command detection works."""

    def test_rm_rf_is_dangerous(self):
        assert is_dangerous("rm -rf /tmp/foo") is True

    def test_rm_recursive_uppercase_is_dangerous(self):
        assert is_dangerous("rm -R /some/dir") is True

    def test_sudo_is_dangerous(self):
        assert is_dangerous("sudo apt-get install foo") is True

    def test_dd_is_dangerous(self):
        assert is_dangerous("dd if=/dev/zero of=/dev/sda") is True

    def test_mkfs_is_dangerous(self):
        assert is_dangerous("mkfs.ext4 /dev/sdb1") is True

    def test_shred_is_dangerous(self):
        assert is_dangerous("shred /dev/sda") is True

    def test_reboot_is_dangerous(self):
        assert is_dangerous("reboot") is True

    def test_shutdown_is_dangerous(self):
        assert is_dangerous("shutdown -h now") is True

    def test_killall_is_dangerous(self):
        assert is_dangerous("killall python") is True

    def test_ls_is_safe(self):
        assert is_dangerous("ls -la") is False

    def test_grep_is_safe(self):
        assert is_dangerous("grep -r pattern .") is False

    def test_find_is_safe(self):
        assert is_dangerous("find . -name '*.py'") is False

    def test_cat_is_safe(self):
        assert is_dangerous("cat /etc/hosts") is False

    def test_git_status_is_safe(self):
        assert is_dangerous("git status") is False


class TestLooksLikeShell:
    """VAL-CLI-012: Non-shell response rejection works."""

    def test_python_import_rejected(self):
        assert looks_like_shell("import os") is False

    def test_python_from_import_rejected(self):
        assert looks_like_shell("from pathlib import Path") is False

    def test_python_def_rejected(self):
        assert looks_like_shell("def hello():") is False

    def test_python_class_rejected(self):
        assert looks_like_shell("class MyClass:") is False

    def test_html_rejected(self):
        assert looks_like_shell("<html>") is False

    def test_php_rejected(self):
        assert looks_like_shell("<?php echo 'hi';") is False

    def test_valid_shell_accepted(self):
        assert looks_like_shell("ls -la") is True

    def test_find_command_accepted(self):
        assert looks_like_shell("find . -name '*.py' -exec wc -l {} +") is True

    def test_pipe_accepted(self):
        assert looks_like_shell("cat file.txt | grep pattern") is True

    def test_git_command_accepted(self):
        assert looks_like_shell("git log --oneline -10") is True

    def test_empty_string_accepted(self):
        """Empty string doesn't match any non-shell pattern, so it's accepted."""
        assert looks_like_shell("") is True


# ── Config action tests (VAL-CLI-013 through VAL-CLI-015, VAL-CLI-019) ───────


@patch("vox.cli.init_config")
@patch("vox.cli.console")
def test_config_init_creates_template(mock_console, mock_init):
    """VAL-CLI-013: config init calls init_config and prints path."""
    mock_init.return_value = Path("/home/user/.config/vox/config.toml")
    args = argparse.Namespace(config_action="init")
    cfg = VoxConfig()
    cmd_config(args, cfg)
    mock_init.assert_called_once()
    # Verify output mentions the path
    mock_console.print.assert_called()
    printed = str(mock_console.print.call_args)
    assert "config.toml" in printed or "Config created" in printed


@patch("vox.cli.CONFIG_FILE")
@patch("vox.cli.console")
def test_config_show_displays_toml(mock_console, mock_file):
    """VAL-CLI-014: config show displays TOML content when config exists."""
    mock_file.is_file.return_value = True
    mock_file.read_text.return_value = "[model]\nname = 'test'\n"
    args = argparse.Namespace(config_action="show")
    cfg = VoxConfig()
    cmd_config(args, cfg)
    mock_console.print.assert_called()


@patch("vox.cli.CONFIG_FILE")
@patch("vox.cli.console")
def test_config_show_hint_when_missing(mock_console, mock_file):
    """VAL-CLI-014: config show shows hint when no config file."""
    mock_file.is_file.return_value = False
    args = argparse.Namespace(config_action="show")
    cfg = VoxConfig()
    cmd_config(args, cfg)
    printed = str(mock_console.print.call_args)
    assert "No config file found" in printed or "vox config init" in printed


@patch("vox.cli.console")
def test_config_path_prints_path(mock_console):
    """VAL-CLI-015: config path prints the config file path."""
    args = argparse.Namespace(config_action="path")
    cfg = VoxConfig()
    cmd_config(args, cfg)
    mock_console.print.assert_called_once()
    printed = str(mock_console.print.call_args)
    assert "config.toml" in printed


@patch("vox.cli.os.execvp")
@patch("vox.cli.CONFIG_FILE")
@patch("vox.cli.init_config")
def test_config_edit_launches_editor(mock_init, mock_file, mock_execvp):
    """VAL-CLI-019: config edit calls os.execvp with EDITOR env var."""
    mock_file.is_file.return_value = True
    args = argparse.Namespace(config_action="edit")
    cfg = VoxConfig()
    with patch.dict(os.environ, {"EDITOR": "vim"}, clear=False):
        cmd_config(args, cfg)
    mock_execvp.assert_called_once()
    call_args = mock_execvp.call_args[0]
    assert call_args[0] == "vim"


@patch("vox.cli.os.execvp")
@patch("vox.cli.CONFIG_FILE")
@patch("vox.cli.init_config")
def test_config_edit_creates_config_if_missing(mock_init, mock_file, mock_execvp):
    """VAL-CLI-019: config edit creates config first if missing."""
    mock_file.is_file.return_value = False
    args = argparse.Namespace(config_action="edit")
    cfg = VoxConfig()
    with patch.dict(os.environ, {"EDITOR": "nano"}, clear=False):
        cmd_config(args, cfg)
    mock_init.assert_called_once()
    mock_execvp.assert_called_once()


@patch("vox.cli.os.execvp")
@patch("vox.cli.CONFIG_FILE")
def test_config_edit_defaults_to_nano(mock_file, mock_execvp):
    """VAL-CLI-019: config edit defaults to nano when EDITOR not set."""
    mock_file.is_file.return_value = True
    args = argparse.Namespace(config_action="edit")
    cfg = VoxConfig()
    env = os.environ.copy()
    env.pop("EDITOR", None)
    with patch.dict(os.environ, env, clear=True):
        cmd_config(args, cfg)
    mock_execvp.assert_called_once()
    call_args = mock_execvp.call_args[0]
    assert call_args[0] == "nano"


# ── Agent subcommand tests (VAL-CLI-016 through VAL-CLI-018) ─────────────────


@patch("vox.agents.router.discover_agents")
@patch("vox.cli.console")
def test_agent_list_shows_agents(mock_console, mock_discover):
    """VAL-CLI-016: agent --list shows discovered agents."""
    mock_discover.return_value = {"claude": "/usr/bin/claude", "codex": "/usr/bin/codex"}
    args = argparse.Namespace(list=True, task=[], use=None)
    cfg = VoxConfig()
    cmd_agent(args, cfg)
    mock_discover.assert_called_once()
    # Should print agent names
    calls = [str(c) for c in mock_console.print.call_args_list]
    printed_text = " ".join(calls)
    assert "claude" in printed_text
    assert "codex" in printed_text


@patch("vox.agents.router.discover_agents")
@patch("vox.cli.console")
def test_agent_list_no_agents(mock_console, mock_discover):
    """VAL-CLI-016: agent --list shows 'No agents found' when none available."""
    mock_discover.return_value = {}
    args = argparse.Namespace(list=True, task=[], use=None)
    cfg = VoxConfig()
    cmd_agent(args, cfg)
    printed = str(mock_console.print.call_args)
    assert "No agents found" in printed


@patch("vox.agents.router.route_and_run")
@patch("vox.cli.console")
def test_agent_no_task_prints_hint(mock_console, mock_route):
    """VAL-CLI-017: agent with no task prints usage hint."""
    args = argparse.Namespace(list=False, task=[], use=None)
    cfg = VoxConfig()
    cmd_agent(args, cfg)
    mock_route.assert_not_called()
    printed = str(mock_console.print.call_args)
    assert "No task provided" in printed


@patch("vox.agents.router.route_and_run")
@patch("vox.cli.console")
def test_agent_use_flag_sets_env(mock_console, mock_route):
    """VAL-CLI-018: agent --use sets VOX_PREFERRED_AGENT env var."""
    mock_route.return_value = "done"
    args = argparse.Namespace(list=False, task=["fix", "tests"], use="claude")
    cfg = VoxConfig()
    original = os.environ.get("VOX_PREFERRED_AGENT")
    try:
        cmd_agent(args, cfg)
        assert os.environ.get("VOX_PREFERRED_AGENT") == "claude"
        mock_route.assert_called_once()
    finally:
        if original is None:
            os.environ.pop("VOX_PREFERRED_AGENT", None)
        else:
            os.environ["VOX_PREFERRED_AGENT"] = original


@patch("vox.agents.router.route_and_run")
@patch("vox.cli.console")
def test_agent_delegates_task(mock_console, mock_route):
    """Agent delegates task to route_and_run with joined task string."""
    mock_route.return_value = "Agent output"
    args = argparse.Namespace(list=False, task=["fix", "the", "tests"], use=None)
    cfg = VoxConfig()
    cmd_agent(args, cfg)
    mock_route.assert_called_once()
    call_args = mock_route.call_args[0]
    assert call_args[0] == "fix the tests"


# ── handle_command tests ─────────────────────────────────────────────────────


@patch("vox.engine.translate")
@patch("vox.cli.console")
def test_handle_command_too_long_query(mock_console, mock_translate):
    """handle_command rejects queries longer than 1000 chars."""
    cfg = VoxConfig()
    handle_command("x" * 1001, cfg)
    mock_translate.assert_not_called()
    printed = str(mock_console.print.call_args)
    assert "too long" in printed.lower()


@patch("vox.cli.prompt_action", return_value="skip")
@patch("vox.engine.translate", return_value="ls -la")
@patch("vox.cli.console")
def test_handle_command_translates_and_shows(mock_console, mock_translate, mock_prompt):
    """handle_command translates query and shows the command."""
    cfg = VoxConfig()
    handle_command("list files", cfg)
    mock_translate.assert_called_once_with("list files", cfg)


@patch("vox.engine.translate", return_value=None)
@patch("vox.cli.console")
def test_handle_command_none_response(mock_console, mock_translate):
    """handle_command shows error when translate returns None."""
    cfg = VoxConfig()
    handle_command("query", cfg)
    printed = str(mock_console.print.call_args)
    assert "Could not translate" in printed


@patch("vox.engine.translate", return_value="import os")
@patch("vox.cli.console")
def test_handle_command_non_shell_rejected(mock_console, mock_translate):
    """handle_command rejects non-shell responses."""
    cfg = VoxConfig()
    handle_command("query", cfg)
    printed = str(mock_console.print.call_args)
    assert "shell command" in printed.lower() or "didn't look like" in printed.lower()
