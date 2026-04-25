from __future__ import annotations

from enum import StrEnum


class NodeKind(StrEnum):
    ROOT = "root"
    PROMPT = "prompt"
    FORK = "fork"
    MERGE = "merge"
    RESOLUTION = "resolution"
    IMPORT = "import"
    MANUAL = "manual"


class NodeStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CODE_CONFLICTED = "code_conflicted"
    CONTEXT_CONFLICTED = "context_conflicted"
    BOTH_CONFLICTED = "both_conflicted"


class CodeMergeSnapshotRole(StrEnum):
    INTEGRATION = "integration"
    CONFLICTED_WORKSPACE = "conflicted_workspace"


class ContextMergeSnapshotRole(StrEnum):
    MERGED_CONTEXT = "merged_context"
    CONFLICTED_CONTEXT_CANDIDATE = "conflicted_context_candidate"


class MergeResolutionPolicy(StrEnum):
    SUCCESSOR_NODE = "successor_node"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeKind(StrEnum):
    NOOP = "noop"
    LOCAL_SUBPROCESS = "local_subprocess"
    PI = "pi"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    CUSTOM = "custom"


class RuntimeCapability(StrEnum):
    RPC_STREAMING = "rpc_streaming"
    CANCELLATION = "cancellation"
    SESSION_PERSISTENCE = "session_persistence"
    SESSION_CLONE = "session_clone"
    STEERING = "steering"
    FOLLOW_UP = "follow_up"
    CUSTOM_TOOLS = "custom_tools"
    IMAGE_INPUT = "image_input"
    MODEL_SWITCHING = "model_switching"


class ContextItemStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"


class ContextSection(StrEnum):
    GOALS = "goals"
    CONSTRAINTS = "constraints"
    DECISIONS = "decisions"
    ASSUMPTIONS = "assumptions"
    OPEN_QUESTIONS = "open_questions"
    TODOS = "todos"
    RISKS = "risks"
    HANDOFF_NOTES = "handoff_notes"


class ContextResolutionChoice(StrEnum):
    SOURCE = "source"
    TARGET = "target"
    ANCESTOR = "ancestor"
    SYNTHESIZED = "synthesized"


class ArtifactKind(StrEnum):
    RUNTIME_TRANSCRIPT = "runtime_transcript"
    RUNTIME_SESSION = "runtime_session"
    CONTEXT_PROJECTION_REPORT = "context_projection_report"
    MERGE_REPORT = "merge_report"
    DIFF_SUMMARY = "diff_summary"
    RESOLUTION_REPORT = "resolution_report"
    RUNTIME_STDERR = "runtime_stderr"
    RAW_RUNTIME_EVENT_LOG = "raw_runtime_event_log"


class EventTopic(StrEnum):
    PROJECT_OPENED = "project_opened"
    ROOT_NODE_CREATED = "root_node_created"
    RUN_CREATED = "run_created"
    RUN_STARTED = "run_started"
    RUN_SUCCEEDED = "run_succeeded"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    RUNTIME_EVENT = "runtime_event"
    ARTIFACT_CREATED = "artifact_created"
    PROMPT_NODE_CREATED = "prompt_node_created"
    MERGE_NODE_CREATED = "merge_node_created"
    RESOLUTION_NODE_CREATED = "resolution_node_created"
