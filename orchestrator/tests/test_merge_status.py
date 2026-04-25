"""Unit coverage for the merge status classifier.

End-to-end coverage of CONTEXT_CONFLICTED now lives in test_merge_flow.py, driven
by runtimes that emit ContextItemEdit. These tests still exercise the classifier
in isolation so status derivation stays pinned to its inputs and not to upstream
projection behaviour.
"""

from __future__ import annotations

from uuid import uuid4

from agentsofchaos_orchestrator.application.merges import _merge_status
from agentsofchaos_orchestrator.domain.enums import NodeStatus
from agentsofchaos_orchestrator.domain.models import ContextConflict


def _conflict(section: str = "goals") -> ContextConflict:
    return ContextConflict(
        section=section,
        item_id=uuid4(),
        explanation=f"Conflicting {section} item.",
    )


def test_merge_status_clean() -> None:
    assert _merge_status(code_conflicts=(), context_conflicts=()) is NodeStatus.READY


def test_merge_status_code_only() -> None:
    assert (
        _merge_status(code_conflicts=("file.txt",), context_conflicts=())
        is NodeStatus.CODE_CONFLICTED
    )


def test_merge_status_context_only() -> None:
    assert (
        _merge_status(code_conflicts=(), context_conflicts=(_conflict(),))
        is NodeStatus.CONTEXT_CONFLICTED
    )


def test_merge_status_both_conflicted() -> None:
    assert (
        _merge_status(
            code_conflicts=("file.txt",),
            context_conflicts=(_conflict(), _conflict("decisions")),
        )
        is NodeStatus.BOTH_CONFLICTED
    )


def test_merge_status_multiple_code_conflicts_without_context() -> None:
    assert (
        _merge_status(
            code_conflicts=("a.txt", "b.txt", "c.txt"),
            context_conflicts=(),
        )
        is NodeStatus.CODE_CONFLICTED
    )


def test_merge_status_multiple_context_conflicts_without_code() -> None:
    assert (
        _merge_status(
            code_conflicts=(),
            context_conflicts=(_conflict("goals"), _conflict("decisions"), _conflict("risks")),
        )
        is NodeStatus.CONTEXT_CONFLICTED
    )
