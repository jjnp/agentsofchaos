"""Unit tests for the pi-runtime context projector.

The projector mines a pi session's `generated_messages` for evidence
the agent inspected files (`read` tool calls + a narrow set of bash
readers). Output flows through `RuntimeExecutionResult.read_file_paths`
into the `ContextSnapshot.read_files` projection.
"""

from __future__ import annotations

from agentsofchaos_orchestrator.infrastructure.runtime.pi.projection import (
    extract_read_file_paths,
)


def _assistant_with_tool_calls(*tool_calls: dict[str, object]) -> dict[str, object]:
    return {"role": "assistant", "content": [{"type": "toolCall", **tc} for tc in tool_calls]}


def test_extracts_paths_from_read_tool_calls() -> None:
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "look at the layout"}]},
        _assistant_with_tool_calls(
            {"name": "read", "arguments": {"path": "src/lib/agent-graph/layout.ts"}}
        ),
        _assistant_with_tool_calls(
            {"name": "read", "arguments": {"path": "src/lib/orchestrator/contracts.ts"}}
        ),
    ]
    paths = extract_read_file_paths(messages)
    assert paths == (
        "src/lib/agent-graph/layout.ts",
        "src/lib/orchestrator/contracts.ts",
    )


def test_deduplicates_repeated_reads_and_preserves_first_appearance_order() -> None:
    messages = [
        _assistant_with_tool_calls(
            {"name": "read", "arguments": {"path": "a.ts"}},
            {"name": "read", "arguments": {"path": "b.ts"}},
            {"name": "read", "arguments": {"path": "a.ts"}},
        ),
        _assistant_with_tool_calls(
            {"name": "read", "arguments": {"path": "c.ts"}},
            {"name": "read", "arguments": {"path": "b.ts"}},
        ),
    ]
    assert extract_read_file_paths(messages) == ("a.ts", "b.ts", "c.ts")


def test_strips_leading_dot_slash() -> None:
    messages = [
        _assistant_with_tool_calls({"name": "read", "arguments": {"path": "./README.md"}})
    ]
    assert extract_read_file_paths(messages) == ("README.md",)


def test_extracts_paths_from_bash_cat_head_tail() -> None:
    messages = [
        _assistant_with_tool_calls(
            {"name": "bash", "arguments": {"command": "cat src/main.py"}},
            {"name": "bash", "arguments": {"command": "head -n 50 README.md"}},
            {"name": "bash", "arguments": {"command": "tail -20 logs/app.log"}},
        )
    ]
    assert extract_read_file_paths(messages) == (
        "src/main.py",
        "README.md",
        "logs/app.log",
    )


def test_skips_bash_commands_with_pipes_redirects_or_substitution() -> None:
    """Anything that needs real shell semantics is too risky to parse —
    rather than guess wrong, we drop the whole command. Provenance
    that's not provably correct is worse than no provenance.
    """
    messages = [
        _assistant_with_tool_calls(
            {"name": "bash", "arguments": {"command": "cat foo.txt | grep bar"}},
            {"name": "bash", "arguments": {"command": "cat $(ls)"}},
            {"name": "bash", "arguments": {"command": "cat foo > bar"}},
            {"name": "bash", "arguments": {"command": "head -n 5 a.txt && tail b.txt"}},
        )
    ]
    assert extract_read_file_paths(messages) == ()


def test_skips_non_read_tool_calls() -> None:
    """Tools that mutate (write/edit) or query the agent (queue, prompt)
    are not evidence the agent *read* a file. `touched_files` carries
    write evidence via the orchestrator's git diff.
    """
    messages = [
        _assistant_with_tool_calls(
            {"name": "write", "arguments": {"path": "out.txt", "content": "x"}},
            {"name": "edit", "arguments": {"path": "in.txt", "patch": "..."}},
            {"name": "bash", "arguments": {"command": "ls -la"}},
            {"name": "bash", "arguments": {"command": "rm bad.txt"}},
        )
    ]
    assert extract_read_file_paths(messages) == ()


def test_ignores_non_assistant_messages() -> None:
    """User and tool-result messages can name file paths in their text
    content, but those aren't the agent reading the file — they're the
    user pointing at it or the tool reporting back. Only the
    `assistant`-emitted toolCall block counts as a read action.
    """
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "open foo.py"}]},
        {
            "role": "toolResult",
            "toolName": "read",
            "content": [{"type": "text", "text": "contents of bar.py"}],
        },
    ]
    assert extract_read_file_paths(messages) == ()


def test_handles_malformed_messages_gracefully() -> None:
    """Sessions sometimes carry weird half-formed messages (e.g. legacy
    schema, extension noise). Don't blow up — just skip them.
    """
    messages = [
        {},
        {"role": "assistant"},
        {"role": "assistant", "content": "not a list"},
        {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
        _assistant_with_tool_calls(
            {"name": "read", "arguments": "not a dict"},
            {"name": "read", "arguments": {}},
            {"name": "read", "arguments": {"path": "ok.txt"}},
        ),
    ]
    assert extract_read_file_paths(messages) == ("ok.txt",)
