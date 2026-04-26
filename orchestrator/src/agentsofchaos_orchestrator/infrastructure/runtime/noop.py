from __future__ import annotations

import re

from agentsofchaos_orchestrator.domain.enums import RuntimeCapability, RuntimeKind
from agentsofchaos_orchestrator.infrastructure.runtime.base import (
    RuntimeEvent,
    RuntimeEventSink,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)

# Tiny "fixture mode": when the prompt contains a line matching
# `<filename>:<content>` the noop runtime writes that file in the
# worktree. Pattern is intentionally narrow — bare filenames only,
# no path traversal, no whitespace, no slashes — so normal prompts
# ("write some docs", "first prompt") still take the default no-op
# path. Line-scanning (rather than full-string match) lets the same
# fixture pattern work even when the orchestrator's resolution prompt
# wraps the user intent inside boilerplate.
_FILE_PROMPT_LINE_RE = re.compile(r"^(?P<name>[\w.\-]+\.[\w]+):(?P<content>.+)$")


def _extract_file_directive(prompt: str) -> tuple[str, str] | None:
    for line in prompt.splitlines():
        stripped = line.strip()
        match = _FILE_PROMPT_LINE_RE.match(stripped)
        if match:
            return match.group("name"), match.group("content")
    return None


class NoOpRuntimeAdapter:
    @property
    def runtime_kind(self) -> RuntimeKind:
        return RuntimeKind.NOOP

    @property
    def capabilities(self) -> frozenset[RuntimeCapability]:
        return frozenset({RuntimeCapability.CANCELLATION})

    async def probe(self) -> None:
        # No external dependencies — the no-op runtime always works.
        return None

    async def execute(
        self,
        *,
        request: RuntimeExecutionRequest,
        emit: RuntimeEventSink,
    ) -> RuntimeExecutionResult:
        request.cancellation_token.throw_if_cancelled()
        await emit(
            RuntimeEvent(
                kind="runtime.started",
                message="No-op runtime started.",
                payload={"worktree_path": str(request.worktree_path)},
            )
        )

        wrote_path: str | None = None
        directive = _extract_file_directive(request.prompt)
        if directive is not None:
            name, content = directive
            target = request.worktree_path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content + ("\n" if not content.endswith("\n") else ""))
            wrote_path = str(target)
            await emit(
                RuntimeEvent(
                    kind="runtime.file_written",
                    message=f"No-op runtime wrote {name}.",
                    payload={"path": wrote_path},
                )
            )

        await emit(
            RuntimeEvent(
                kind="runtime.completed",
                message="No-op runtime completed.",
                payload={},
            )
        )
        request.cancellation_token.throw_if_cancelled()
        return RuntimeExecutionResult(
            transcript_text=f"USER: {request.prompt}\nASSISTANT: No-op runtime executed.\n",
            summary_text=(
                f"No-op runtime wrote {directive[0]}"
                if directive is not None
                else f"No-op prompt execution for: {request.prompt}"
            ),
        )
