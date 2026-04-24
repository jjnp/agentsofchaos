from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from agentsofchaos_orchestrator_v2.domain.enums import RunStatus, RuntimeKind
from agentsofchaos_orchestrator_v2.domain.models import Run
from agentsofchaos_orchestrator_v2.domain.run_policy import (
    InvalidRunTransitionError,
    RunLifecyclePolicy,
)


def build_run(status: RunStatus) -> Run:
    return Run(
        id=uuid4(),
        project_id=uuid4(),
        source_node_id=uuid4(),
        prompt="test",
        status=status,
        runtime=RuntimeKind.CUSTOM,
    )


def test_run_lifecycle_allows_normal_success_path() -> None:
    policy = RunLifecyclePolicy()
    started_at = datetime.now(timezone.utc)
    finished_at = datetime.now(timezone.utc)

    running = policy.start(build_run(RunStatus.QUEUED), started_at=started_at)
    succeeded = policy.succeed(
        running,
        transcript_path="/tmp/transcript.log",
        finished_at=finished_at,
    )

    assert running.status is RunStatus.RUNNING
    assert running.started_at == started_at
    assert succeeded.status is RunStatus.SUCCEEDED
    assert succeeded.transcript_path == "/tmp/transcript.log"
    assert succeeded.finished_at == finished_at


def test_run_lifecycle_allows_running_to_cancelled() -> None:
    policy = RunLifecyclePolicy()
    finished_at = datetime.now(timezone.utc)
    running = build_run(RunStatus.RUNNING)

    cancelled = policy.cancel(running, finished_at=finished_at)

    assert cancelled.status is RunStatus.CANCELLED
    assert cancelled.finished_at == finished_at


def test_run_lifecycle_rejects_terminal_transition() -> None:
    policy = RunLifecyclePolicy()

    with pytest.raises(InvalidRunTransitionError):
        policy.start(build_run(RunStatus.SUCCEEDED), started_at=datetime.now(timezone.utc))
