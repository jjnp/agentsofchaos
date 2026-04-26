from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import FileResponse, Response, StreamingResponse

from agentsofchaos_orchestrator.api.dependencies import (
    get_event_bus,
    get_orchestrator_service,
    get_settings,
)
from agentsofchaos_orchestrator.api.schemas import (
    ArtifactListResponse,
    ArtifactResponse,
    CodeSnapshotResponse,
    ContextDiffResponse,
    ContextDiffTotalsResponse,
    ContextItemDiffResponse,
    ContextItemResponse,
    ContextSectionDiffResponse,
    ContextSnapshotResponse,
    DiffHunkResponse,
    DiffLineResponse,
    DiffTotalsResponse,
    EventResponse,
    FileDiffResponse,
    GraphResponse,
    MergeNodesRequest,
    MergeReportResponse,
    MergeResponse,
    NodeDiffResponse,
    NodeResponse,
    OpenProjectRequest,
    ProjectResponse,
    PromptRunRequest,
    RunResponse,
)
from agentsofchaos_orchestrator.application.context_diff import ContextDiff, ContextItemDiff
from agentsofchaos_orchestrator.application.diffs import FileDiff, NodeDiff
from agentsofchaos_orchestrator.application.services import OrchestratorService
from agentsofchaos_orchestrator.domain.errors import NodeNotFoundError, RunNotFoundError
from agentsofchaos_orchestrator.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator.infrastructure.settings import Settings

router = APIRouter(prefix="/projects", tags=["projects"])
ServiceDependency = Annotated[OrchestratorService, Depends(get_orchestrator_service)]
EventBusDependency = Annotated[InMemoryEventBus, Depends(get_event_bus)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
OptionalUuidQuery = Annotated[UUID | None, Query()]


@router.post("/open", response_model=ProjectResponse, status_code=201)
async def open_project(
    request: OpenProjectRequest,
    service: ServiceDependency,
) -> ProjectResponse:
    """Open or re-open a project, ensuring it has a root node.

    Validates the path is a git repository, registers the project (or
    returns the existing one if already opened), and creates a root
    node from `HEAD` if none exists yet. The returned `Project` does
    not embed the root — fetch `GET /projects/{id}/graph` to enumerate
    nodes. Subsequent calls with the same path are idempotent.
    """
    project = await service.open_project(Path(request.path))
    return ProjectResponse.from_domain(project)


@router.get("/{project_id}/graph", response_model=GraphResponse)
async def get_graph(
    project_id: UUID,
    service: ServiceDependency,
) -> GraphResponse:
    graph = await service.get_graph(project_id)
    return GraphResponse.from_domain(graph)


@router.post("/{project_id}/nodes/root", response_model=NodeResponse, status_code=201)
async def create_root_node(
    project_id: UUID,
    service: ServiceDependency,
) -> NodeResponse:
    """Idempotent root-node creation. Returns the existing root if any.

    `POST /projects/open` already creates the root from `HEAD` so most
    clients never need this endpoint. It stays as a safety net for the
    rare case where opening a project produced no root (e.g. an
    operator-recovery flow), and is safe to retry — calling it on a
    project that already has a root returns that root unchanged. Status
    is 201 in both cases for backward compatibility.
    """
    node = await service.create_root_node(project_id)
    return NodeResponse.from_domain(node)


@router.get("/{project_id}/nodes/{node_id}", response_model=NodeResponse)
async def get_node(
    project_id: UUID,
    node_id: UUID,
    service: ServiceDependency,
) -> NodeResponse:
    node = await service.get_node(project_id=project_id, node_id=node_id)
    return NodeResponse.from_domain(node)


@router.get("/{project_id}/nodes/{node_id}/archive")
async def get_node_archive(
    project_id: UUID,
    node_id: UUID,
    service: ServiceDependency,
) -> Response:
    """Stream a tar of the full tree at this node's code snapshot.

    Wraps `git archive --format=tar <sha>`. The whole tree comes back
    as one downloadable artifact — useful for "give me the entire
    state at this node" without cloning the project repo. Filename is
    `node-<short_sha>.tar`.
    """
    archive, commit_sha = await service.archive_node(
        project_id=project_id, node_id=node_id
    )
    filename = f"node-{commit_sha[:12]}.tar"
    return Response(
        content=archive,
        media_type="application/x-tar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/{project_id}/nodes/{node_id}/files/{path:path}/content")
async def get_node_file_content(
    project_id: UUID,
    node_id: UUID,
    path: str,
    service: ServiceDependency,
) -> Response:
    """Stream raw bytes of a file at this node's code snapshot.

    Resolves node → code snapshot → commit, then `git cat-file blob`s
    the requested path. Binary-safe (returns `application/octet-stream`).
    A `Content-Disposition: attachment` header lets the browser save
    the file with its basename. Use this to download any file the
    agent created or modified at the node — the diff endpoint already
    shows what changed; this gets you the actual content.
    """
    content = await service.read_node_file(
        project_id=project_id, node_id=node_id, path=path
    )
    filename = Path(path).name or "download"
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/{project_id}/code-snapshots/{snapshot_id}",
    response_model=CodeSnapshotResponse,
)
async def get_code_snapshot(
    project_id: UUID,
    snapshot_id: UUID,
    service: ServiceDependency,
) -> CodeSnapshotResponse:
    snapshot = await service.get_code_snapshot(
        project_id=project_id, snapshot_id=snapshot_id
    )
    return CodeSnapshotResponse.from_domain(snapshot)


@router.get(
    "/{project_id}/context-snapshots/{snapshot_id}",
    response_model=ContextSnapshotResponse,
)
async def get_context_snapshot(
    project_id: UUID,
    snapshot_id: UUID,
    service: ServiceDependency,
) -> ContextSnapshotResponse:
    snapshot = await service.get_context_snapshot(
        project_id=project_id, snapshot_id=snapshot_id
    )
    return ContextSnapshotResponse.from_domain(snapshot)


def _file_diff_to_response(file: FileDiff) -> FileDiffResponse:
    return FileDiffResponse(
        path=file.path,
        old_path=file.old_path,
        new_path=file.new_path,
        change_type=file.change_type,
        additions=file.additions,
        deletions=file.deletions,
        hunks=tuple(
            DiffHunkResponse(
                header=hunk.header,
                old_start=hunk.old_start,
                old_lines=hunk.old_lines,
                new_start=hunk.new_start,
                new_lines=hunk.new_lines,
                lines=tuple(
                    DiffLineResponse(type=line.type, content=line.content)
                    for line in hunk.lines
                ),
            )
            for hunk in file.hunks
        ),
    )


def _node_diff_to_response(diff: NodeDiff) -> NodeDiffResponse:
    files_count, additions, deletions = diff.totals
    return NodeDiffResponse(
        node_id=diff.node_id,
        base_commit_sha=diff.base_commit_sha,
        head_commit_sha=diff.head_commit_sha,
        totals=DiffTotalsResponse(
            files=files_count, additions=additions, deletions=deletions
        ),
        files=tuple(_file_diff_to_response(file) for file in diff.files),
    )


@router.get(
    "/{project_id}/nodes/{node_id}/diff",
    response_model=NodeDiffResponse,
)
async def get_node_diff(
    project_id: UUID,
    node_id: UUID,
    service: ServiceDependency,
) -> NodeDiffResponse:
    diff = await service.get_node_diff(project_id=project_id, node_id=node_id)
    return _node_diff_to_response(diff)


def _context_item_diff_to_response(item: ContextItemDiff) -> ContextItemDiffResponse:
    return ContextItemDiffResponse(
        item_id=item.item_id,
        change_type=item.change_type,
        before=ContextItemResponse.model_validate(item.before.model_dump())
        if item.before is not None
        else None,
        after=ContextItemResponse.model_validate(item.after.model_dump())
        if item.after is not None
        else None,
    )


def _context_diff_to_response(diff: ContextDiff) -> ContextDiffResponse:
    sections = tuple(
        ContextSectionDiffResponse(
            section=section.section.value,
            additions=section.additions,
            removals=section.removals,
            changes=section.changes,
            items=tuple(_context_item_diff_to_response(item) for item in section.items),
        )
        for section in diff.sections
    )
    totals = ContextDiffTotalsResponse(
        additions=sum(section.additions for section in sections),
        removals=sum(section.removals for section in sections),
        changes=sum(section.changes for section in sections),
    )
    return ContextDiffResponse(
        node_id=diff.node_id,
        base_snapshot_id=diff.base_snapshot_id,
        head_snapshot_id=diff.head_snapshot_id,
        totals=totals,
        sections=sections,
    )


@router.get(
    "/{project_id}/nodes/{node_id}/context-diff",
    response_model=ContextDiffResponse,
)
async def get_node_context_diff(
    project_id: UUID,
    node_id: UUID,
    service: ServiceDependency,
) -> ContextDiffResponse:
    diff = await service.get_node_context_diff(project_id=project_id, node_id=node_id)
    return _context_diff_to_response(diff)


@router.post(
    "/{project_id}/nodes/{node_id}/runs/prompt",
    response_model=RunResponse,
    status_code=201,
)
async def prompt_node(
    project_id: UUID,
    node_id: UUID,
    request: PromptRunRequest,
    service: ServiceDependency,
) -> RunResponse:
    graph = await service.get_graph(project_id)
    if all(node.id != node_id for node in graph.nodes):
        raise NodeNotFoundError(f"Node {node_id} does not belong to project {project_id}")

    run = await service.start_prompt_run(node_id, request.prompt)
    return RunResponse.from_domain(run)


@router.post("/{project_id}/merges", response_model=MergeResponse, status_code=201)
async def merge_nodes(
    project_id: UUID,
    request: MergeNodesRequest,
    service: ServiceDependency,
) -> MergeResponse:
    result = await service.merge_nodes(
        project_id=project_id,
        source_node_id=request.source_node_id,
        target_node_id=request.target_node_id,
        title=request.title,
    )
    return MergeResponse(
        node=NodeResponse.from_domain(result.node),
        ancestor_node_id=result.ancestor_node.id,
        code_conflicts=result.code_conflicts,
        context_conflicts=tuple(
            conflict.model_dump(mode="json") for conflict in result.context_conflicts
        ),
        code_snapshot_role=result.code_snapshot_role,
        context_snapshot_role=result.context_snapshot_role,
        resolution_policy=result.resolution_policy,
        report_path=str(result.report_path),
    )


@router.get(
    "/{project_id}/merges/{node_id}/report",
    response_model=MergeReportResponse,
)
async def get_merge_report(
    project_id: UUID,
    node_id: UUID,
    service: ServiceDependency,
) -> MergeReportResponse:
    report = await service.get_merge_report(project_id=project_id, node_id=node_id)
    return MergeReportResponse(report=report)


@router.post(
    "/{project_id}/merges/{node_id}/resolution-runs/prompt",
    response_model=RunResponse,
    status_code=201,
)
async def prompt_merge_resolution(
    project_id: UUID,
    node_id: UUID,
    request: PromptRunRequest,
    service: ServiceDependency,
) -> RunResponse:
    run = await service.start_merge_resolution_prompt_run(
        project_id=project_id,
        merge_node_id=node_id,
        prompt=request.prompt,
    )
    return RunResponse.from_domain(run)


@router.get("/{project_id}/runs/{run_id}", response_model=RunResponse)
async def get_run(
    project_id: UUID,
    run_id: UUID,
    service: ServiceDependency,
) -> RunResponse:
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise RunNotFoundError(f"Run {run_id} does not belong to project {project_id}")
    return RunResponse.from_domain(run)


@router.post("/{project_id}/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    project_id: UUID,
    run_id: UUID,
    service: ServiceDependency,
) -> RunResponse:
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise RunNotFoundError(f"Run {run_id} does not belong to project {project_id}")
    await service.cancel_run(run_id)
    return RunResponse.from_domain(await service.get_run(run_id))


@router.get("/{project_id}/events", response_model=tuple[EventResponse, ...])
async def list_project_events(
    project_id: UUID,
    service: ServiceDependency,
) -> tuple[EventResponse, ...]:
    events = await service.list_events(project_id)
    return tuple(EventResponse.from_domain(event) for event in events)


@router.get("/{project_id}/events/stream")
async def stream_project_events(
    project_id: UUID,
    service: ServiceDependency,
    event_bus: EventBusDependency,
    settings: SettingsDependency,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    after_id: Annotated[UUID | None, Query()] = None,
) -> StreamingResponse:
    """SSE event stream with replay-on-reconnect.

    Each frame carries an `id:` line so the browser's EventSource
    automatically resends `Last-Event-ID` when it reconnects. Replay
    cursor sources, in priority order:
      1. `Last-Event-ID` request header (browser auto-reconnect path)
      2. `?after_id=<uuid>` query param (manual / cross-session
         resume — the header is hard to set on EventSource)
      3. neither — fall back to full historical replay (initial connect)

    Race-free wiring: we subscribe to the event bus *before* querying
    historical, so any event written between the cursor and the
    subscription is captured by the queue. We then de-dupe live events
    against the historical batch by id, so callers see each event
    exactly once even on the boundary tick.
    """
    cursor: UUID | None = None
    if last_event_id:
        try:
            cursor = UUID(last_event_id.strip())
        except ValueError:
            cursor = None
    if cursor is None and after_id is not None:
        cursor = after_id

    async def event_generator() -> AsyncIterator[str]:
        async with event_bus.subscribe(project_id) as queue:
            replayed_ids: set[UUID] = set()
            historical: tuple[EventResponse, ...]
            if cursor is not None:
                since = await service.list_events_since(
                    project_id, after_event_id=cursor
                )
                if since is None:
                    # Anchor missing — honour the SSE contract by
                    # falling back to a full replay rather than silently
                    # dropping the gap.
                    historical = tuple(
                        EventResponse.from_domain(e)
                        for e in await service.list_events(project_id)
                    )
                else:
                    historical = tuple(EventResponse.from_domain(e) for e in since)
            else:
                historical = tuple(
                    EventResponse.from_domain(e)
                    for e in await service.list_events(project_id)
                )

            for event in historical:
                replayed_ids.add(event.id)
                yield _format_sse_frame(event)

            while True:
                try:
                    live_event = await asyncio.wait_for(
                        queue.get(),
                        timeout=settings.event_stream_keepalive_seconds,
                    )
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                live_response = EventResponse.from_domain(live_event)
                if live_response.id in replayed_ids:
                    # Already streamed in the historical batch — the
                    # subscribe-before-query window picked it up twice.
                    continue
                replayed_ids.add(live_response.id)
                yield _format_sse_frame(live_response)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def _format_sse_frame(event: EventResponse) -> str:
    """SSE frame with `id:` line so EventSource tracks Last-Event-ID."""
    return (
        f"id: {event.id}\n"
        f"event: {event.topic.value}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


def _artifact_to_response(artifact: object) -> ArtifactResponse:
    return ArtifactResponse.model_validate(artifact.model_dump())  # type: ignore[attr-defined]


@router.get(
    "/{project_id}/artifacts",
    response_model=ArtifactListResponse,
)
async def list_artifacts(
    project_id: UUID,
    service: ServiceDependency,
    node_id: OptionalUuidQuery = None,
    run_id: OptionalUuidQuery = None,
) -> ArtifactListResponse:
    artifacts = await service.list_artifacts(
        project_id, node_id=node_id, run_id=run_id
    )
    return ArtifactListResponse(
        artifacts=tuple(_artifact_to_response(artifact) for artifact in artifacts),
    )


@router.get(
    "/{project_id}/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
)
async def get_artifact(
    project_id: UUID,
    artifact_id: UUID,
    service: ServiceDependency,
) -> ArtifactResponse:
    artifact = await service.get_artifact(
        project_id=project_id, artifact_id=artifact_id
    )
    return _artifact_to_response(artifact)


@router.get(
    "/{project_id}/artifacts/{artifact_id}/content",
)
async def get_artifact_content(
    project_id: UUID,
    artifact_id: UUID,
    service: ServiceDependency,
) -> FileResponse:
    artifact = await service.get_artifact(
        project_id=project_id, artifact_id=artifact_id
    )
    return FileResponse(
        path=artifact.path,
        media_type=artifact.media_type,
        filename=Path(artifact.path).name,
    )
