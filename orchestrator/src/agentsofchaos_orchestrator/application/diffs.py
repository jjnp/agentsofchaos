from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.queries import QueryService
from agentsofchaos_orchestrator.domain.errors import ProjectNotFoundError
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class DiffLine:
    type: str  # 'context' | 'add' | 'remove'
    content: str


@dataclass(frozen=True)
class DiffHunk:
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: tuple[DiffLine, ...]


@dataclass(frozen=True)
class FileDiff:
    path: str
    old_path: str
    new_path: str
    change_type: str  # 'modified' | 'added' | 'deleted' | 'renamed'
    additions: int
    deletions: int
    hunks: tuple[DiffHunk, ...]


@dataclass(frozen=True)
class NodeDiff:
    node_id: UUID
    base_commit_sha: str | None
    head_commit_sha: str
    files: tuple[FileDiff, ...]

    @property
    def totals(self) -> tuple[int, int, int]:
        files = len(self.files)
        additions = sum(file.additions for file in self.files)
        deletions = sum(file.deletions for file in self.files)
        return files, additions, deletions


_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def _strip_prefix(path: str) -> str:
    """Strip the conventional `a/` or `b/` prefix that `git diff` adds."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_unified_diff(text: str) -> tuple[FileDiff, ...]:
    """
    Parse a `git diff --unified=N` text block into structured FileDiffs.
    Tolerates: rename headers, file mode lines, deleted/new file modes,
    binary diff markers (these become files with empty hunks).
    """
    if not text.strip():
        return ()

    files: list[FileDiff] = []
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.startswith("diff --git "):
            index += 1
            continue

        # Header parsing.
        old_path: str | None = None
        new_path: str | None = None
        change_type = "modified"
        is_binary = False

        index += 1
        while index < len(lines):
            current = lines[index]
            if current.startswith("diff --git "):
                break
            if current.startswith("new file mode"):
                change_type = "added"
            elif current.startswith("deleted file mode"):
                change_type = "deleted"
            elif current.startswith("rename from "):
                old_path = current[len("rename from ") :]
                change_type = "renamed"
            elif current.startswith("rename to "):
                new_path = current[len("rename to ") :]
            elif current.startswith("--- "):
                marker = current[len("--- ") :]
                if marker != "/dev/null":
                    old_path = _strip_prefix(marker)
            elif current.startswith("+++ "):
                marker = current[len("+++ ") :]
                if marker != "/dev/null":
                    new_path = _strip_prefix(marker)
            elif current.startswith("Binary files "):
                is_binary = True
            elif current.startswith("@@ "):
                break
            index += 1

        # Hunks.
        hunks: list[DiffHunk] = []
        additions = 0
        deletions = 0
        while index < len(lines):
            current = lines[index]
            if current.startswith("diff --git "):
                break
            if not current.startswith("@@ "):
                index += 1
                continue
            match = _HUNK_HEADER_RE.match(current)
            if not match:
                index += 1
                continue
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1
            header = current

            index += 1
            hunk_lines: list[DiffLine] = []
            while index < len(lines):
                hl = lines[index]
                if hl.startswith("diff --git ") or hl.startswith("@@ "):
                    break
                if hl.startswith("\\"):
                    # e.g. "\ No newline at end of file"
                    index += 1
                    continue
                if hl.startswith("+"):
                    hunk_lines.append(DiffLine(type="add", content=hl[1:]))
                    additions += 1
                elif hl.startswith("-"):
                    hunk_lines.append(DiffLine(type="remove", content=hl[1:]))
                    deletions += 1
                elif hl.startswith(" "):
                    hunk_lines.append(DiffLine(type="context", content=hl[1:]))
                else:
                    # Stray line; treat as context to avoid losing data.
                    hunk_lines.append(DiffLine(type="context", content=hl))
                index += 1

            hunks.append(
                DiffHunk(
                    header=header,
                    old_start=old_start,
                    old_lines=old_count,
                    new_start=new_start,
                    new_lines=new_count,
                    lines=tuple(hunk_lines),
                )
            )

        if not new_path and old_path:
            new_path = old_path
        if not old_path and new_path:
            old_path = new_path
        primary_path = new_path or old_path or "<unknown>"
        if is_binary and not hunks:
            # Surface binary changes as a single zero-line file entry.
            pass

        files.append(
            FileDiff(
                path=primary_path,
                old_path=old_path or primary_path,
                new_path=new_path or primary_path,
                change_type=change_type,
                additions=additions,
                deletions=deletions,
                hunks=tuple(hunks),
            )
        )

    return tuple(files)


class DiffApplicationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        git_service: GitService,
        queries: QueryService,
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._git_service = git_service
        self._queries = queries

    async def get_node_diff(self, *, project_id: UUID, node_id: UUID) -> NodeDiff:
        node = await self._queries.get_node(project_id=project_id, node_id=node_id)

        async with self._unit_of_work() as unit_of_work:
            project = await unit_of_work.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Unknown project: {project_id}")
            repository_root = Path(project.root_path)

            head_snapshot = await unit_of_work.code_snapshots.get(node.code_snapshot_id)
            if head_snapshot is None:
                # Should not happen in a healthy graph.
                raise ProjectNotFoundError(
                    f"Code snapshot {node.code_snapshot_id} missing for node {node_id}"
                )
            head_sha = head_snapshot.commit_sha

            base_sha: str | None = None
            if node.parent_node_ids:
                # Use the structural parent (last) for diff context — matches the
                # canvas layout convention.
                parent_id = node.parent_node_ids[-1]
                parent = await unit_of_work.nodes.get(parent_id)
                if parent is not None:
                    parent_snapshot = await unit_of_work.code_snapshots.get(
                        parent.code_snapshot_id
                    )
                    if parent_snapshot is not None:
                        base_sha = parent_snapshot.commit_sha

        diff_text = self._git_service.unified_diff(
            repository_root,
            from_commit=base_sha,
            to_commit=head_sha,
        )
        files = parse_unified_diff(diff_text)
        return NodeDiff(
            node_id=node_id,
            base_commit_sha=base_sha,
            head_commit_sha=head_sha,
            files=files,
        )
