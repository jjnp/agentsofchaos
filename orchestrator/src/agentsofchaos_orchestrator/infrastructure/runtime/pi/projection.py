from __future__ import annotations

import shlex
from collections.abc import Sequence

from agentsofchaos_orchestrator.infrastructure.runtime.pi.events import (
    JsonObject,
    optional_object_dict,
    optional_object_list,
    optional_str,
)


# Bash sub-commands we'll mine for read-evidence — the positional
# argument(s) after flags are paths. Anything outside this whitelist
# (build commands, test runners, mutators, ...) is ignored: false
# positives would muddy `read_files` provenance.
_BASH_READ_COMMANDS: frozenset[str] = frozenset(
    {"cat", "head", "tail", "less", "more", "type"}
)
# Short flags whose value is the *next* token (e.g. `head -n 50`).
# Anything not in this set we treat as a boolean flag — no value to
# skip past — which is the conservative behaviour for unknown flags.
_BASH_FLAGS_WITH_VALUE: frozenset[str] = frozenset(
    {"-n", "-c", "-N", "-C", "--lines", "--bytes"}
)


def extract_read_file_paths(messages: Sequence[JsonObject]) -> tuple[str, ...]:
    """Walk a pi session's messages, return every file path the agent read.

    Sources, in priority order:

    1. Tool calls named `read` — the canonical "look at this file"
       primitive. Path is the `path` argument.
    2. Tool calls named `bash` whose first command is `cat`/`head`/
       `tail`/`less`/`more` and which take a single positional path.
       Best-effort — anything more elaborate (pipelines, redirects,
       multi-arg) is skipped rather than guessed.

    Returned paths are deduplicated, order-stable by first appearance,
    and stripped of leading `./`. Caller is responsible for resolving
    them relative to the worktree if absolute paths are needed.
    """
    seen: dict[str, None] = {}
    for message in messages:
        if optional_str(message.get("role")) != "assistant":
            continue
        for block in optional_object_list(message.get("content")):
            if optional_str(block.get("type")) != "toolCall":
                continue
            tool_name = optional_str(block.get("name"))
            arguments = optional_object_dict(block.get("arguments"))
            if arguments is None:
                continue
            for path in _paths_from_tool_call(tool_name, arguments):
                seen.setdefault(path, None)
    return tuple(seen)


def _paths_from_tool_call(
    tool_name: str | None, arguments: JsonObject
) -> tuple[str, ...]:
    if tool_name == "read":
        path = optional_str(arguments.get("path"))
        return (_normalize_path(path),) if path else ()
    if tool_name == "bash":
        command = optional_str(arguments.get("command"))
        if not command:
            return ()
        return _paths_from_bash_command(command)
    return ()


def _paths_from_bash_command(command: str) -> tuple[str, ...]:
    """Best-effort extraction from a bash one-liner.

    Skips anything with shell pipes, redirects, conditionals, or
    command substitution — those almost always need real shell
    semantics to interpret. The narrow case we do handle is
    ``<reader> [flags] <single-path>`` for the readers in
    ``_BASH_READ_COMMANDS``.
    """
    if any(bad in command for bad in ("|", ">", "<", "&&", "||", ";", "$(", "`")):
        return ()
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ()
    if not tokens:
        return ()
    head = tokens[0]
    if head not in _BASH_READ_COMMANDS:
        return ()
    paths: list[str] = []
    skip_next = False
    for token in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            # Inline `--lines=50` style — single token, no value to skip.
            if "=" in token:
                continue
            if token in _BASH_FLAGS_WITH_VALUE:
                skip_next = True
            continue
        paths.append(_normalize_path(token))
    return tuple(paths)


def _normalize_path(path: str) -> str:
    stripped = path.strip()
    if stripped.startswith("./"):
        stripped = stripped[2:]
    return stripped
