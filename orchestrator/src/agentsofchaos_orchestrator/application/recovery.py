from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
import logging
import shutil

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentsofchaos_orchestrator.application.eventing import ApplicationEventRecorder
from agentsofchaos_orchestrator.domain.enums import EventTopic, RunStatus
from agentsofchaos_orchestrator.domain.models import Run
from agentsofchaos_orchestrator.domain.run_policy import RunLifecyclePolicy
from agentsofchaos_orchestrator.infrastructure.git_service import GitService
from agentsofchaos_orchestrator.infrastructure.settings import Settings
from agentsofchaos_orchestrator.infrastructure.unit_of_work import UnitOfWorkFactory

logger = logging.getLogger(__name__)


class StartupRecoveryService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        git_service: GitService,
        events: ApplicationEventRecorder,
        now: Callable[[], datetime],
    ) -> None:
        self._unit_of_work = UnitOfWorkFactory(session_factory)
        self._settings = settings
        self._git_service = git_service
        self._events = events
        self._now = now
        self._lifecycle = RunLifecyclePolicy()

    async def reconcile_interrupted_runs(self) -> int:
        async with self._unit_of_work() as unit_of_work:
            interrupted_runs = await unit_of_work.runs.list_by_statuses(
                (RunStatus.QUEUED, RunStatus.RUNNING)
            )

        reconciled = 0
        for run in interrupted_runs:
            await self._reconcile_run(run)
            reconciled += 1
        return reconciled

    async def cleanup_stale_worktrees(self) -> int:
        async with self._unit_of_work() as unit_of_work:
            projects = await unit_of_work.projects.list_all()

        removed = 0
        for project in projects:
            project_root = Path(project.root_path)
            worktree_root = self._settings.daemon_state_dir_for_project(project_root)
            worktree_root = worktree_root / "worktrees"
            if not worktree_root.is_dir():
                continue
            for child in worktree_root.iterdir():
                if not child.exists():
                    continue
                try:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                    removed += 1
                except Exception:
                    logger.exception(
                        "Failed to remove stale AoC worktree",
                        extra={"worktree_path": str(child)},
                    )
            try:
                self._git_service.prune_worktrees(project_root)
            except Exception:
                logger.exception(
                    "Failed to prune git worktree metadata",
                    extra={"project_root": str(project_root)},
                )
        return removed

    async def _reconcile_run(self, run: Run) -> None:
        if run.status is RunStatus.QUEUED:
            await self._cancel_stale_queued_run(run)
            return
        if run.status is RunStatus.RUNNING:
            await self._fail_interrupted_running_run(run)

    async def _cancel_stale_queued_run(self, run: Run) -> None:
        timestamp = self._now()
        cancelled_run = self._lifecycle.cancel(run, finished_at=timestamp)
        async with self._unit_of_work() as unit_of_work:
            persisted = await unit_of_work.runs.update(cancelled_run)
            event = await unit_of_work.events.add(
                project_id=persisted.project_id,
                topic=EventTopic.RUN_CANCELLED,
                payload={
                    "projectId": str(persisted.project_id),
                    "runId": str(persisted.id),
                    "cancelled": True,
                    "recovered": True,
                    "reason": "stale queued run during startup recovery",
                },
                created_at=timestamp,
            )
            await unit_of_work.outbox.add_from_event(event)
            await unit_of_work.commit()
        await self._events.dispatch_pending()

    async def _fail_interrupted_running_run(self, run: Run) -> None:
        timestamp = self._now()
        error_message = "Run interrupted by daemon shutdown or crash"
        failed_run = self._lifecycle.fail(
            run,
            error_message=error_message,
            finished_at=timestamp,
        )
        async with self._unit_of_work() as unit_of_work:
            persisted = await unit_of_work.runs.update(failed_run)
            event = await unit_of_work.events.add(
                project_id=persisted.project_id,
                topic=EventTopic.RUN_FAILED,
                payload={
                    "projectId": str(persisted.project_id),
                    "runId": str(persisted.id),
                    "error": error_message,
                    "recovered": True,
                    "reason": "interrupted running run during startup recovery",
                },
                created_at=timestamp,
            )
            await unit_of_work.outbox.add_from_event(event)
            await unit_of_work.commit()
        await self._events.dispatch_pending()
