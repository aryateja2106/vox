#!/usr/bin/env python3
"""Build NL-to-shell training dataset from multiple sources.

Sources:
  1. Curated examples (inline) — tmux, docker, git, kubectl, etc.
  2. NL2Bash dataset (if available)
  3. tldr pages (if cloned locally)

Output: JSONL file with {"instruction": "...", "output": "..."} pairs.

Usage:
  python scripts/finetune/build_dataset.py --output data/nl2shell.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CURATED_EXAMPLES = [
    # tmux
    ("create a new tmux session named work", "tmux new-session -s work"),
    ("list all tmux sessions", "tmux list-sessions"),
    ("attach to tmux session named dev", "tmux attach-session -t dev"),
    ("kill tmux session named test", "tmux kill-session -t test"),
    ("split tmux pane vertically", "tmux split-window -v"),
    ("split tmux pane horizontally", "tmux split-window -h"),
    ("detach from current tmux session", "tmux detach-client"),
    ("rename current tmux window to editor", "tmux rename-window editor"),
    ("switch to tmux window 2", "tmux select-window -t 2"),
    ("create tmux session named droid and start in ~/Projects", "tmux new-session -s droid -c ~/Projects"),
    # git
    ("show git log as one line per commit", "git log --oneline"),
    ("create a new branch called feature-auth", "git checkout -b feature-auth"),
    ("delete branch feature-old", "git branch -d feature-old"),
    ("show files changed in last commit", "git diff --name-only HEAD~1"),
    ("undo last commit but keep changes", "git reset --soft HEAD~1"),
    ("stash current changes with message", "git stash push -m 'wip: auth refactor'"),
    ("show all remote branches", "git branch -r"),
    ("cherry pick commit abc123", "git cherry-pick abc123"),
    ("rebase current branch on main", "git rebase main"),
    ("show blame for file auth.py", "git blame auth.py"),
    # docker
    ("list running docker containers", "docker ps"),
    ("stop all running containers", "docker stop $(docker ps -q)"),
    ("remove all stopped containers", "docker container prune -f"),
    ("build docker image tagged myapp", "docker build -t myapp ."),
    ("run container from myapp image with port 8080", "docker run -p 8080:8080 myapp"),
    ("show docker container logs for web", "docker logs web"),
    ("exec bash in running container web", "docker exec -it web bash"),
    ("list docker images", "docker images"),
    ("pull the latest nginx image", "docker pull nginx:latest"),
    ("remove docker image myapp", "docker rmi myapp"),
    # kubernetes
    ("get all pods in default namespace", "kubectl get pods"),
    ("describe pod named api-server", "kubectl describe pod api-server"),
    ("get logs from pod api-server", "kubectl logs api-server"),
    ("apply kubernetes config from deploy.yaml", "kubectl apply -f deploy.yaml"),
    ("delete pod named crashed-pod", "kubectl delete pod crashed-pod"),
    ("scale deployment api to 3 replicas", "kubectl scale deployment api --replicas=3"),
    ("port forward pod api-server to local port 8080", "kubectl port-forward pod/api-server 8080:8080"),
    # file operations
    ("find all python files in current directory", "find . -name '*.py' -type f"),
    ("count lines in all python files", "find . -name '*.py' | xargs wc -l"),
    ("find files larger than 100MB", "find . -size +100M -type f"),
    ("compress directory src into archive", "tar -czf src.tar.gz src/"),
    ("extract tar.gz file", "tar -xzf archive.tar.gz"),
    ("find and replace foo with bar in all py files", "find . -name '*.py' -exec sed -i '' 's/foo/bar/g' {} +"),
    ("show disk usage of current directory", "du -sh ."),
    ("show disk space on all drives", "df -h"),
    ("watch a file for changes", "tail -f /var/log/syslog"),
    ("create directory structure src/components/auth", "mkdir -p src/components/auth"),
    # process management
    ("find process using port 8080", "lsof -i :8080"),
    ("kill process with pid 1234", "kill 1234"),
    ("show top 10 memory consuming processes", "ps aux --sort=-%mem | head -11"),
    ("show all processes matching python", "pgrep -fl python"),
    ("run command in background", "nohup ./server.sh &"),
    # network
    ("check if google.com is reachable", "ping -c 3 google.com"),
    ("show all listening ports", "lsof -i -P | grep LISTEN"),
    ("download file from url", "curl -O https://example.com/file.tar.gz"),
    ("make http GET request to localhost api", "curl http://localhost:8080/api/health"),
    ("show my public ip address", "curl -s ifconfig.me"),
    # python/dev
    ("create a python virtual environment", "python3 -m venv .venv"),
    ("activate virtual environment", "source .venv/bin/activate"),
    ("install requirements from file", "pip install -r requirements.txt"),
    ("run pytest with verbose output", "pytest -v"),
    ("run ruff linter on src directory", "ruff check src/"),
    ("start python http server on port 8000", "python3 -m http.server 8000"),
    ("check python version", "python3 --version"),
    # system
    ("show system info", "uname -a"),
    ("show current date and time", "date"),
    ("show environment variables", "env"),
    ("add directory to PATH", "export PATH=$PATH:/new/path"),
    ("show command history", "history"),
    ("repeat last command", "!!"),
    ("show who is logged in", "who"),
    # text processing
    ("search for pattern in files recursively", "grep -rn 'pattern' ."),
    ("count occurrences of word in file", "grep -c 'word' file.txt"),
    ("sort file and remove duplicates", "sort file.txt | uniq"),
    ("show first 20 lines of file", "head -20 file.txt"),
    ("show last 50 lines of log", "tail -50 app.log"),
    ("extract column 2 from csv", "cut -d',' -f2 data.csv"),
    ("convert json to pretty format", "cat data.json | python3 -m json.tool"),
]


def build_from_curated() -> list[dict]:
    return [{"instruction": nl, "output": sh} for nl, sh in CURATED_EXAMPLES]


def build_from_tldr(tldr_path: Path) -> list[dict]:
    """Parse tldr pages directory for NL/shell pairs."""
    pairs = []
    pages_dir = tldr_path / "pages" / "common"
    if not pages_dir.exists():
        pages_dir = tldr_path / "pages"

    if not pages_dir.exists():
        return pairs

    for md_file in pages_dir.rglob("*.md"):
        lines = md_file.read_text().splitlines()
        description = None
        for line in lines:
            if line.startswith("> ") and not line.startswith("> More"):
                description = line[2:].strip().rstrip(".")
            elif line.startswith("`") and line.endswith("`") and description:
                command = line[1:-1]
                if "{{" not in command:
                    pairs.append({"instruction": description, "output": command})
                description = None

    return pairs


def main():
    parser = argparse.ArgumentParser(description="Build NL-to-shell training dataset")
    parser.add_argument("--output", "-o", default="data/nl2shell.jsonl", help="Output JSONL path")
    parser.add_argument("--tldr", default=None, help="Path to cloned tldr-pages repo")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_pairs = build_from_curated()
    print(f"Curated examples: {len(all_pairs)}")

    if args.tldr:
        tldr_pairs = build_from_tldr(Path(args.tldr))
        print(f"tldr pages: {len(tldr_pairs)}")
        all_pairs.extend(tldr_pairs)

    seen = set()
    unique = []
    for pair in all_pairs:
        key = (pair["instruction"].lower(), pair["output"])
        if key not in seen:
            seen.add(key)
            unique.append(pair)

    with open(output_path, "w") as f:
        for pair in unique:
            f.write(json.dumps(pair) + "\n")

    print(f"Total unique pairs: {len(unique)}")
    print(f"Written to: {output_path}")


if __name__ == "__main__":
    main()
