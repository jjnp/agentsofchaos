from __future__ import annotations

from pathlib import Path

from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from tests.helpers import initialize_test_repository, run_git, write_and_commit_file


def test_merge_base_resolves_common_ancestor(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    git_service = GitService()

    ancestor_commit = run_git(repository_root, "rev-parse", "HEAD")

    run_git(repository_root, "checkout", "-b", "feature-left")
    left_commit = write_and_commit_file(
        repository_root,
        relative_path="left.txt",
        content="left\n",
        message="left change",
    )

    run_git(repository_root, "checkout", "main")
    run_git(repository_root, "checkout", "-b", "feature-right")
    right_commit = write_and_commit_file(
        repository_root,
        relative_path="right.txt",
        content="right\n",
        message="right change",
    )

    merge_base = git_service.merge_base(repository_root, left_commit, right_commit)

    assert merge_base == ancestor_commit


def test_create_and_remove_detached_worktree(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_test_repository(repository_root)
    git_service = GitService()

    head_commit = run_git(repository_root, "rev-parse", "HEAD")
    worktree_path = tmp_path / "worktree"

    worktree = git_service.create_detached_worktree(
        repository_root,
        worktree_path=worktree_path,
        commit_sha=head_commit,
    )

    assert worktree.path == worktree_path.resolve()
    assert worktree.head_commit == head_commit
    assert (worktree.path / "README.md").is_file()

    git_service.remove_worktree(repository_root, worktree_path=worktree.path)

    assert not worktree.path.exists()
