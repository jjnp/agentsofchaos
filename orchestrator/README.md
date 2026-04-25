# Agents of Chaos Orchestrator

This directory is the **fresh-start Python implementation** of Agents of Chaos.

It intentionally supersedes the earlier Python rewrite attempt. This is the only sanctioned path for the orchestrator.

## What it is

Agents of Chaos is a **local-first daemon** for a browser-native graph of agent work.

Its core model is:

- the **graph is the product**
- **nodes are immutable**
- **runs are ephemeral**
- every node carries both a **code snapshot** and a **context snapshot**
- code and context merges both reconcile from a **common ancestor**

## What it is not

It is not:

- a container orchestrator with graph UI on top
- a mutable chat session with branch-like decoration
- a thin wrapper around one specific agent CLI
- a “summary only” memory layer

## Status

This folder started docs-first and now contains the **initial implementation foundation**:

- Python package skeleton
- FastAPI app factory
- SQLite persistence setup
- typed domain models
- git repository validation
- project registration
- root node creation from `HEAD`
- detached worktree lifecycle and merge-base utilities
- supervised background prompt-run execution with cancellation
- pluggable runtime adapters, with pi as the first rich adapter
- durable event records, outbox dispatch, and SSE event streaming
- first ancestor-based merge subsystem for code and context
- initial tests for project opening, root node creation, git worktrees, prompt runs, and merges

The implementation is intentionally moving phase by phase. The foundation is in place; merge handling now exists as a first cut and still needs richer conflict UX, deeper context semantics, and frontend wiring.

## Read these first

1. `AGENT.md` — engineering rules for anyone working in this folder
2. `docs/manifesto.md` — product philosophy and non-negotiable principles
3. `docs/architecture.md` — system shape, components, and invariants
4. `docs/runtime-adapters.md` — multi-runtime strategy with pi first, not pi only
5. `docs/context-model.md` — first-class context model and merge semantics
6. `docs/implementation-plan.md` — phased execution plan and quality gates
7. `docs/adrs/` — initial architecture decisions

## Intended stack

- Python 3.12+
- FastAPI for local HTTP API
- SQLite for durable local state
- SQLAlchemy 2.x for persistence
- Pydantic 2 for typed IO boundaries
- AnyIO / asyncio for concurrency
- Git CLI, wrapped behind a typed service boundary
- Runtime adapters for pi first, with room for Claude Code and Codex later
- strict Ruff + mypy + pytest guardrails

## Directory layout

```text
orchestrator/
  AGENT.md
  README.md
  pyproject.toml
  docs/
    manifesto.md
    architecture.md
    runtime-adapters.md
    context-model.md
    implementation-plan.md
    adrs/
  src/
    agentsofchaos_orchestrator/
  tests/
```

## Implementation intent

The first implementation target is a high-quality local daemon that can:

- open a repository and create a root node from `HEAD`
- run an agent prompt from a node into a fresh child node
- persist code snapshots and context snapshots as first-class state
- stream run events live to the browser
- merge two nodes into an integration node using common-ancestor semantics for both code and context
- expose a clean, typed API to the browser UI

## Rule of engagement

If implementation pressure ever conflicts with the architectural invariants, **the implementation must bend**.

The point of this rewrite is not speed at any cost.
The point is to build a trustworthy foundation.
