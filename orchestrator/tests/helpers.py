from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def initialize_test_repository(repository_root: Path) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    run_git(repository_root, "init", "-b", "main")
    run_git(repository_root, "config", "user.name", "Agents of Chaos Tests")
    run_git(repository_root, "config", "user.email", "tests@agentsofchaos.local")
    write_and_commit_file(
        repository_root,
        relative_path="README.md",
        content="# fixture\n",
        message="initial commit",
    )


def write_and_commit_file(
    repository_root: Path,
    *,
    relative_path: str,
    content: str,
    message: str,
) -> str:
    target_path = repository_root / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    run_git(repository_root, "add", relative_path)
    run_git(repository_root, "commit", "-m", message)
    return run_git(repository_root, "rev-parse", "HEAD")
