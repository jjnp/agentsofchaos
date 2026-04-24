from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from agentsofchaos_orchestrator_v2.api.dependencies import (
    get_event_bus,
    get_orchestrator_service,
    get_settings,
)
from agentsofchaos_orchestrator_v2.api.schemas import (
    CodeSnapshotResponse,
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
from agentsofchaos_orchestrator_v2.application.diffs import FileDiff, NodeDiff
from agentsofchaos_orchestrator_v2.application.services import OrchestratorService
from agentsofchaos_orchestrator_v2.domain.errors import NodeNotFoundError, RunNotFoundError
from agentsofchaos_orchestrator_v2.infrastructure.event_bus import InMemoryEventBus
from agentsofchaos_orchestrator_v2.infrastructure.settings import Settings

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/open", response_model=ProjectResponse, status_code=201)
async def open_project(
    request: OpenProjectRequest,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> ProjectResponse:
    project = await service.open_project(Path(request.path))
    return ProjectResponse.from_domain(project)


@router.get("/{project_id}/graph", response_model=GraphResponse)
async def get_graph(
    project_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> GraphResponse:
    graph = await service.get_graph(project_id)
    return GraphResponse.from_domain(graph)


@router.post("/{project_id}/nodes/root", response_model=NodeResponse, status_code=201)
async def create_root_node(
    project_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> NodeResponse:
    node = await service.create_root_node(project_id)
    return NodeResponse.from_domain(node)


@router.get("/{project_id}/nodes/{node_id}", response_model=NodeResponse)
async def get_node(
    project_id: UUID,
    node_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> NodeResponse:
    node = await service.get_node(project_id=project_id, node_id=node_id)
    return NodeResponse.from_domain(node)


@router.get(
    "/{project_id}/code-snapshots/{snapshot_id}",
    response_model=CodeSnapshotResponse,
)
async def get_code_snapshot(
    project_id: UUID,
    snapshot_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
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
    service: OrchestratorService = Depends(get_orchestrator_service),
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
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> NodeDiffResponse:
    diff = await service.get_node_diff(project_id=project_id, node_id=node_id)
    return _node_diff_to_response(diff)


@router.post(
    "/{project_id}/nodes/{node_id}/runs/prompt",
    response_model=RunResponse,
    status_code=201,
)
async def prompt_node(
    project_id: UUID,
    node_id: UUID,
    request: PromptRunRequest,
    service: OrchestratorService = Depends(get_orchestrator_service),
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
    service: OrchestratorService = Depends(get_orchestrator_service),
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
        context_conflicts=result.context_conflicts,
        report_path=str(result.report_path),
    )


@router.get(
    "/{project_id}/merges/{node_id}/report",
    response_model=MergeReportResponse,
)
async def get_merge_report(
    project_id: UUID,
    node_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> MergeReportResponse:
    report = await service.get_merge_report(project_id=project_id, node_id=node_id)
    return MergeReportResponse(report=report)


@router.get("/{project_id}/runs/{run_id}", response_model=RunResponse)
async def get_run(
    project_id: UUID,
    run_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> RunResponse:
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise RunNotFoundError(f"Run {run_id} does not belong to project {project_id}")
    return RunResponse.from_domain(run)


@router.post("/{project_id}/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    project_id: UUID,
    run_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> RunResponse:
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise RunNotFoundError(f"Run {run_id} does not belong to project {project_id}")
    await service.cancel_run(run_id)
    return RunResponse.from_domain(await service.get_run(run_id))


@router.get("/{project_id}/events", response_model=tuple[EventResponse, ...])
async def list_project_events(
    project_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> tuple[EventResponse, ...]:
    events = await service.list_events(project_id)
    return tuple(EventResponse.from_domain(event) for event in events)


@router.get("/{project_id}/events/stream")
async def stream_project_events(
    project_id: UUID,
    service: OrchestratorService = Depends(get_orchestrator_service),
    event_bus: InMemoryEventBus = Depends(get_event_bus),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    historical_events = await service.list_events(project_id)

    async def event_generator() -> AsyncIterator[str]:
        for event in historical_events:
            payload = EventResponse.from_domain(event).model_dump_json()
            yield f"event: {event.topic.value}\ndata: {payload}\n\n"

        async with event_bus.subscribe(project_id) as queue:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=settings.event_stream_keepalive_seconds,
                    )
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                payload = EventResponse.from_domain(event).model_dump_json()
                yield f"event: {event.topic.value}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
