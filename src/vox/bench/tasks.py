"""Built-in Terminal-Bench 2.0 task definitions.

These tasks are inspired by the Terminal-Bench 2.0 benchmark
(https://www.tbench.ai/) and cover common real-world terminal scenarios.
Each task verifies its own success via a shell command.

Categories: file, text, process, system, archive, network, git, shell
"""

from __future__ import annotations

from vox.bench.harness import Task

BUILTIN_TASKS: list[Task] = [
    # ── file operations ────────────────────────────────────────────────────
    Task(
        id="file-list-hidden",
        description="list all files including hidden ones in the current directory",
        verify_cmd="ls -a | grep -q '\\.'",
        solution="ls -la",
        category="file",
    ),
    Task(
        id="file-count-lines",
        description="count the number of lines in /etc/hosts",
        verify_cmd="[ -f /etc/hosts ]",
        solution="wc -l /etc/hosts",
        category="file",
    ),
    Task(
        id="file-find-large",
        description="find files larger than 1MB in the current directory",
        verify_cmd="true",
        solution="find . -size +1M -type f",
        category="file",
    ),
    Task(
        id="file-disk-usage",
        description="show disk usage of each directory in the current folder sorted by size",
        verify_cmd="true",
        solution="du -sh */ 2>/dev/null | sort -rh",
        category="file",
    ),
    Task(
        id="file-touch-create",
        description="create an empty file named bench_test_file.txt",
        verify_cmd="test -f bench_test_file.txt",
        solution="touch bench_test_file.txt",
        category="file",
        teardown_cmd="rm -f bench_test_file.txt",
    ),
    Task(
        id="file-mkdir-nested",
        description="create nested directories bench_dir/sub/deep",
        verify_cmd="test -d bench_dir/sub/deep",
        solution="mkdir -p bench_dir/sub/deep",
        category="file",
        teardown_cmd="rm -rf bench_dir",
    ),
    Task(
        id="file-find-py",
        description="find all Python files in the current directory recursively",
        verify_cmd="true",
        solution="find . -name '*.py' -type f",
        category="file",
    ),
    # ── text processing ────────────────────────────────────────────────────
    Task(
        id="text-word-count",
        description="count the number of words in /etc/hosts",
        verify_cmd="[ -f /etc/hosts ]",
        solution="wc -w /etc/hosts",
        category="text",
    ),
    Task(
        id="text-grep-pattern",
        description="search for the word 'localhost' in /etc/hosts",
        verify_cmd="grep -q localhost /etc/hosts",
        solution="grep localhost /etc/hosts",
        category="text",
    ),
    Task(
        id="text-sort-file",
        description="sort the lines of /etc/hosts alphabetically and show the result",
        verify_cmd="[ -f /etc/hosts ]",
        solution="sort /etc/hosts",
        category="text",
    ),
    # ── process management ─────────────────────────────────────────────────
    Task(
        id="proc-list-all",
        description="list all running processes with their PIDs",
        verify_cmd="true",
        solution="ps aux",
        category="process",
    ),
    Task(
        id="proc-top-cpu",
        description="show the top 5 processes by CPU usage",
        verify_cmd="true",
        solution="ps aux --sort=-%cpu | head -6",
        category="process",
    ),
    Task(
        id="proc-current-shell",
        description="show the current shell process ID",
        verify_cmd="true",
        solution="echo $$",
        category="process",
    ),
    # ── system info ────────────────────────────────────────────────────────
    Task(
        id="sys-free-space",
        description="show free disk space in human readable format",
        verify_cmd="true",
        solution="df -h",
        category="system",
    ),
    Task(
        id="sys-memory-usage",
        description="show current memory usage",
        verify_cmd="true",
        solution="free -h",
        category="system",
    ),
    Task(
        id="sys-hostname",
        description="print the current hostname",
        verify_cmd="true",
        solution="hostname",
        category="system",
    ),
    Task(
        id="sys-env-path",
        description="print the PATH environment variable",
        verify_cmd="true",
        solution="echo $PATH",
        category="system",
    ),
    # ── archive operations ─────────────────────────────────────────────────
    Task(
        id="archive-create-tar",
        description="create a gzip compressed tar archive of /etc/hosts named hosts.tar.gz",
        verify_cmd="test -f hosts.tar.gz",
        solution="tar czf hosts.tar.gz /etc/hosts",
        category="archive",
        teardown_cmd="rm -f hosts.tar.gz",
    ),
    Task(
        id="archive-list-tar",
        description="list the contents of an archive file hosts.tar.gz",
        setup_cmd="tar czf hosts.tar.gz /etc/hosts",
        verify_cmd="test -f hosts.tar.gz",
        solution="tar tzf hosts.tar.gz",
        category="archive",
        teardown_cmd="rm -f hosts.tar.gz",
    ),
    # ── network ────────────────────────────────────────────────────────────
    Task(
        id="net-check-port",
        description="check if port 80 is open on localhost",
        verify_cmd="true",
        solution="nc -z localhost 80 2>/dev/null; true",
        category="network",
    ),
    Task(
        id="net-dns-lookup",
        description="look up the IP address of example.com",
        verify_cmd="true",
        solution="host example.com 2>/dev/null || nslookup example.com 2>/dev/null || dig example.com +short",
        category="network",
    ),
    # ── git ────────────────────────────────────────────────────────────────
    Task(
        id="git-status",
        description="show the current git repository status",
        verify_cmd="true",
        solution="git status",
        category="git",
    ),
    Task(
        id="git-log-short",
        description="show the last 5 git commits in one-line format",
        verify_cmd="true",
        solution="git log --oneline -5",
        category="git",
    ),
    Task(
        id="git-list-branches",
        description="list all git branches",
        verify_cmd="true",
        solution="git branch -a",
        category="git",
    ),
    # ── shell utilities ────────────────────────────────────────────────────
    Task(
        id="shell-date",
        description="print the current date and time",
        verify_cmd="true",
        solution="date",
        category="shell",
    ),
    Task(
        id="shell-calc",
        description="calculate 2 to the power of 10 using the shell",
        verify_cmd="true",
        solution="echo $((2**10))",
        category="shell",
    ),
    Task(
        id="shell-pipe-count",
        description="count the number of files in /etc",
        verify_cmd="[ -d /etc ]",
        solution="ls /etc | wc -l",
        category="shell",
    ),
]
