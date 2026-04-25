from __future__ import annotations

from dataclasses import dataclass

from agentsofchaos_orchestrator.domain.models import ContextItem, ContextSnapshot, FileReference


@dataclass(frozen=True)
class ContextualPrompt:
    prompt: str
    context_markdown: str
    injected: bool


def build_contextual_prompt(*, prompt: str, source_context: ContextSnapshot) -> ContextualPrompt:
    context_markdown = render_context_snapshot(source_context)
    if not context_markdown.strip():
        return ContextualPrompt(
            prompt=prompt,
            context_markdown="",
            injected=False,
        )
    contextual_prompt = (
        "You are continuing work from an Agents of Chaos immutable graph node.\n"
        "Use the canonical AoC context below as authoritative branch context.\n\n"
        "<aoc_context>\n"
        f"{context_markdown}\n"
        "</aoc_context>\n\n"
        "User prompt:\n"
        f"{prompt}"
    )
    return ContextualPrompt(
        prompt=contextual_prompt,
        context_markdown=context_markdown,
        injected=True,
    )


def render_context_snapshot(context: ContextSnapshot) -> str:
    sections: list[str] = []
    _append_text(sections, "Summary", context.summary)
    _append_items(sections, "Goals", context.goals)
    _append_items(sections, "Constraints", context.constraints)
    _append_items(sections, "Decisions", context.decisions)
    _append_items(sections, "Assumptions", context.assumptions)
    _append_items(sections, "Open questions", context.open_questions)
    _append_items(sections, "Todos", context.todos)
    _append_items(sections, "Risks", context.risks)
    _append_items(sections, "Handoff notes", context.handoff_notes)
    _append_files(sections, "Read files", context.read_files)
    _append_files(sections, "Touched files", context.touched_files)
    return "\n\n".join(sections)


def _append_text(sections: list[str], title: str, text: str) -> None:
    stripped = text.strip()
    if stripped:
        sections.append(f"## {title}\n{stripped}")


def _append_items(sections: list[str], title: str, items: tuple[ContextItem, ...]) -> None:
    active_items = [item for item in items if item.text.strip()]
    if not active_items:
        return
    body = "\n".join(f"- {item.text.strip()}" for item in active_items)
    sections.append(f"## {title}\n{body}")


def _append_files(sections: list[str], title: str, files: tuple[FileReference, ...]) -> None:
    paths = sorted({file.path for file in files if file.path.strip()})
    if not paths:
        return
    body = "\n".join(f"- {path}" for path in paths)
    sections.append(f"## {title}\n{body}")
