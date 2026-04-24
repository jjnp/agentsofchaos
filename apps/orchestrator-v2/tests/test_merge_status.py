"""Unit coverage for the merge status classifier.

End-to-end coverage of CONTEXT_CONFLICTED and BOTH_CONFLICTED currently requires
the context projection service to produce divergent context items across sibling
runs, which it does not yet do (see context_projection.py — every run adds fresh
items with new UUIDs). These tests cover the classifier function in isolation so
status derivation is pinned independently of projection maturity.
"""

from __future__ import annotations

from agentsofchaos_orchestrator_v2.application.merges import _merge_status
from agentsofchaos_orchestrator_v2.domain.enums import NodeStatus


def _conflict(section: str = "goals") -> dict[str, object]:
    return {"kind": "context_item_conflict", "section": section}


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
