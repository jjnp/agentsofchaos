from __future__ import annotations


class OrchestratorError(Exception):
    """Base class for orchestrator domain and application errors."""


class InvalidRepositoryError(OrchestratorError):
    """Raised when a provided path is not a valid git repository."""


class ProjectNotFoundError(OrchestratorError):
    """Raised when a project identifier cannot be resolved."""


class NodeNotFoundError(OrchestratorError):
    """Raised when a node identifier cannot be resolved."""


class SnapshotNotFoundError(OrchestratorError):
    """Raised when a code or context snapshot identifier cannot be resolved."""


class RootNodeAlreadyExistsError(OrchestratorError):
    """Raised when a second root node is requested for a project."""


class RunNotFoundError(OrchestratorError):
    """Raised when a run identifier cannot be resolved."""


class GitOperationError(OrchestratorError):
    """Raised when a git command fails or a git invariant is broken."""


class MergeAncestorError(OrchestratorError):
    """Raised when nodes cannot be merged from a valid common ancestor."""


class MergeInvalidNodesError(OrchestratorError):
    """Raised when merge inputs fail validation (e.g. source==target,
    resolution against a non-merge or non-conflicted node)."""


class RuntimeExecutionError(OrchestratorError):
    """Raised when a runtime adapter cannot complete a run successfully."""


class RuntimeCancelledError(RuntimeExecutionError):
    """Raised when runtime execution is cancelled intentionally."""

    def __init__(
        self,
        message: str,
        *,
        transcript_text: str | None = None,
        runtime_metadata: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.transcript_text = transcript_text
        self.runtime_metadata = runtime_metadata or {}
