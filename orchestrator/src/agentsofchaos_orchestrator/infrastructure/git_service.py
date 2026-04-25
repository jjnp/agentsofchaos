from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from agentsofchaos_orchestrator.domain.errors import GitOperationError, InvalidRepositoryError


@dataclass(frozen=True)
class GitRepositoryInfo:
    root_path: Path
    git_dir: Path
    head_commit: str


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    head_commit: str


@dataclass(frozen=True)
class GitConflictFile:
    path: str
    marker_count: int
    preview: str
    stages: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class GitMergeResult:
    clean: bool
    conflicted_files: tuple[str, ...]
    conflict_details: tuple[GitConflictFile, ...]
    stdout: str
    stderr: str


GitErrorT = TypeVar("GitErrorT", bound=Exception)


class GitService:
    def inspect_repository(self, candidate_path: Path) -> GitRepositoryInfo:
        normalized_path = candidate_path.expanduser().resolve(strict=True)
        if not normalized_path.is_dir():
            raise InvalidRepositoryError(f"Path is not a directory: {normalized_path}")

        root_path = Path(self._git_text(normalized_path, "rev-parse", "--show-toplevel"))
        git_dir = Path(self._git_text(normalized_path, "rev-parse", "--absolute-git-dir"))
        head_commit = self._git_text(normalized_path, "rev-parse", "HEAD")
        if len(head_commit) != 40:
            raise InvalidRepositoryError(
                f"Repository HEAD is not a full commit SHA: {head_commit!r}"
            )

        return GitRepositoryInfo(
            root_path=root_path.resolve(strict=True),
            git_dir=git_dir.resolve(strict=True),
            head_commit=head_commit,
        )

    def ensure_node_ref(self, repository_root: Path, *, ref_name: str, commit_sha: str) -> None:
        self._git(
            repository_root,
            "update-ref",
            ref_name,
            commit_sha,
            error_type=GitOperationError,
        )

    def current_head_commit(self, repository_root: Path) -> str:
        commit_sha = self._git_text(repository_root, "rev-parse", "HEAD")
        return self._ensure_commit_sha(commit_sha)

    def merge_base(self, repository_root: Path, left_commit: str, right_commit: str) -> str:
        merge_base = self._git_text(
            repository_root,
            "merge-base",
            left_commit,
            right_commit,
            error_type=GitOperationError,
        )
        return self._ensure_commit_sha(merge_base)

    def create_detached_worktree(
        self,
        repository_root: Path,
        *,
        worktree_path: Path,
        commit_sha: str,
    ) -> WorktreeInfo:
        resolved_worktree_path = worktree_path.expanduser().resolve()
        if resolved_worktree_path.exists():
            raise GitOperationError(f"Worktree path already exists: {resolved_worktree_path}")

        resolved_worktree_path.parent.mkdir(parents=True, exist_ok=True)
        self._git(
            repository_root,
            "worktree",
            "add",
            "--detach",
            str(resolved_worktree_path),
            commit_sha,
            error_type=GitOperationError,
        )
        head_commit = self.current_head_commit(resolved_worktree_path)
        return WorktreeInfo(path=resolved_worktree_path, head_commit=head_commit)

    def remove_worktree(self, repository_root: Path, *, worktree_path: Path) -> None:
        resolved_worktree_path = worktree_path.expanduser().resolve()
        if resolved_worktree_path.exists():
            self._git(
                repository_root,
                "worktree",
                "remove",
                "--force",
                str(resolved_worktree_path),
                error_type=GitOperationError,
            )
        if resolved_worktree_path.exists():
            shutil.rmtree(resolved_worktree_path)

    def prune_worktrees(self, repository_root: Path) -> None:
        self._git(repository_root, "worktree", "prune", error_type=GitOperationError)

    def has_uncommitted_changes(self, worktree_path: Path) -> bool:
        status_output = self._git_text(worktree_path, "status", "--short")
        return bool(status_output)

    def changed_files_between(
        self,
        repository_root: Path,
        *,
        from_commit: str,
        to_commit: str,
    ) -> tuple[str, ...]:
        output = self._git_text(
            repository_root,
            "diff",
            "--name-only",
            from_commit,
            to_commit,
            error_type=GitOperationError,
        )
        if not output:
            return ()
        return tuple(line for line in output.splitlines() if line)

    EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

    def unified_diff(
        self,
        repository_root: Path,
        *,
        from_commit: str | None,
        to_commit: str,
        context_lines: int = 3,
    ) -> str:
        """
        Produce a unified diff between two commits as raw text. When `from_commit`
        is None, diffs against git's well-known empty-tree SHA, which yields
        every file in `to_commit` as an addition.
        """
        base = from_commit or self.EMPTY_TREE_SHA
        completed = self._git(
            repository_root,
            "diff",
            f"--unified={context_lines}",
            "--no-color",
            "--find-renames",
            base,
            to_commit,
            error_type=GitOperationError,
        )
        return completed.stdout

    def commit_all(self, worktree_path: Path, *, message: str) -> str:
        self._git(worktree_path, "add", "--all", error_type=GitOperationError)
        if not self.has_uncommitted_changes(worktree_path):
            return self.current_head_commit(worktree_path)

        self._git(worktree_path, "commit", "-m", message, error_type=GitOperationError)
        return self.current_head_commit(worktree_path)

    def merge_no_commit(self, worktree_path: Path, *, commit_sha: str) -> GitMergeResult:
        completed = subprocess.run(
            ["git", "merge", "--no-commit", "--no-ff", commit_sha],
            cwd=worktree_path,
            check=False,
            capture_output=True,
            text=True,
        )
        conflicted_files = self.unmerged_files(worktree_path)
        conflict_details = tuple(
            self.conflict_file_details(worktree_path, relative_path)
            for relative_path in conflicted_files
        )
        return GitMergeResult(
            clean=completed.returncode == 0 and not conflicted_files,
            conflicted_files=conflicted_files,
            conflict_details=conflict_details,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )

    def unmerged_files(self, worktree_path: Path) -> tuple[str, ...]:
        output = self._git_text(
            worktree_path,
            "diff",
            "--name-only",
            "--diff-filter=U",
            error_type=GitOperationError,
        )
        if not output:
            return ()
        return tuple(line for line in output.splitlines() if line)

    def conflict_file_details(self, worktree_path: Path, relative_path: str) -> GitConflictFile:
        file_path = worktree_path / relative_path
        content = ""
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8", errors="replace")
        stages = self._conflict_stages(worktree_path, relative_path)
        return GitConflictFile(
            path=relative_path,
            marker_count=content.count("<<<<<<< "),
            preview=content[:4000],
            stages=stages,
        )

    def _conflict_stages(
        self,
        worktree_path: Path,
        relative_path: str,
    ) -> tuple[dict[str, str], ...]:
        output = self._git_text(
            worktree_path,
            "ls-files",
            "-u",
            "--",
            relative_path,
            error_type=GitOperationError,
        )
        stages: list[dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split(maxsplit=3)
            if len(parts) != 4:
                continue
            mode, object_sha, stage, path = parts
            stages.append(
                {"mode": mode, "objectSha": object_sha, "stage": stage, "path": path}
            )
        return tuple(stages)

    def _ensure_commit_sha(self, value: str) -> str:
        if len(value) != 40:
            raise InvalidRepositoryError(f"Value is not a full commit SHA: {value!r}")
        return value

    def _git_text(
        self,
        repository_root: Path,
        *args: str,
        error_type: type[GitErrorT] = InvalidRepositoryError,
    ) -> str:
        completed = self._git(repository_root, *args, error_type=error_type)
        return completed.stdout.strip()

    def _git(
        self,
        repository_root: Path,
        *args: str,
        error_type: type[GitErrorT] = InvalidRepositoryError,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", *args],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            detail = stderr or stdout or "unknown git failure"
            raise error_type(f"git {' '.join(args)} failed in {repository_root}: {detail}")
        return completed
