# Implementation Plan

This document describes how to implement Agents of Chaos without compromising the architecture.

## 1. Implementation philosophy

Build the smallest system that is still faithful to the core invariants.

Do not start by reproducing every feature of the prototype.
Start by building the correct foundation.

Before 1.0, foundational refactors may be large when they make the architecture more durable. This is explicit policy, documented in `docs/adrs/0007-pre-1-0-foundational-refactors.md`.

## 2. Order of work

## Phase 0 — foundation and guardrails

Goal: establish the project skeleton and quality gates before feature work.

Deliverables:
- package layout aligned with architecture docs
- settings model
- logging setup
- Alembic migrations initialized
- Ruff, mypy, pytest, coverage, and CI wiring
- utility boundaries for clock, UUID generation, paths, and subprocess execution
- initial ADR set committed

Quality gates:
- strict mypy passes
- lint passes
- empty test harness passes
- migrations are reproducible

## Phase 1 — durable graph core

Goal: create durable graph primitives without any agent runtime yet.

Deliverables:
- project entity
- node entity
- run entity
- code snapshot entity
- context snapshot entity
- artifact entity
- event record entity
- repositories for persistence
- root node creation from current `HEAD`
- daemon-owned refs under `refs/aoc/nodes/<node-id>`

Tests:
- root node creation
- node immutability invariants
- persistence round-trips
- repository safety boundaries

## Phase 2 — git and worktree engine

Goal: build a trustworthy git substrate before runtime orchestration.

Deliverables:
- typed git service
- common ancestor resolution
- worktree creation and cleanup
- commit capture from worktree
- node diff queries
- merge sandbox creation without context logic yet

Tests:
- common ancestor resolution across branch shapes
- worktree lifecycle
- safe cleanup behavior
- git ref management
- merge sandbox creation

## Phase 3 — runtime adapter and run pipeline

Goal: support prompting a node into a child node with live execution.

Deliverables:
- runtime adapter protocol
- normalized runtime event model
- first adapter implementation (`PiRuntimeAdapter`)
- run lifecycle state machine
- in-process run supervisor for pre-1.0 execution
- runtime-neutral cancellation token
- run cancellation endpoint
- startup reconciliation for interrupted queued/running runs
- partial transcript/session artifact capture for cancellable runtimes
- unit-of-work boundary for durable writes
- event outbox table and dispatch path
- supervised outbox background dispatcher
- transcript/event capture
- SSE event streaming
- provisional running child node creation
- successful child node finalization
- failed/cancelled run handling
- runtime artifact persistence strategy that leaves room for future adapters

Tests:
- run state transitions
- cancellation behavior
- transcript persistence
- event streaming contract
- child node creation on success
- failure behavior with artifact capture

## Phase 4 — typed context projection

Goal: make context first-class for single-parent runs.

Deliverables:
- typed context snapshot domain model
- context item model with provenance
- context projection service from run provenance
- context diff queries
- browser-facing context inspection API

Tests:
- context projection from controlled transcripts
- provenance preservation
- context diff behavior
- serialization round-trips

## Phase 5 — ancestor-based merge

Goal: implement integration-node merge for both code and context.

Deliverables:
- merge service — first cut implemented
- common ancestor selection for node pairs — first cut implemented
- code merge execution in temporary worktree — first cut implemented
- context merge service from ancestor/source/target snapshots — first cut implemented
- merge reports and conflict artifacts — first cut implemented
- integration node creation — first cut implemented
- independent code/context conflict classification — first cut implemented
- richer conflict UX and manual resolution — pending
- merge report retrieval endpoint — implemented
- code conflict detail capture — implemented

Tests:
- clean merge
- code-conflicted merge
- context-conflicted merge
- both-conflicted merge
- artifact generation
- lineage correctness

## Phase 6 — hardening and reconciliation

Goal: make the daemon robust under interruption and failure.

Deliverables:
- startup reconciliation
- stale worktree cleanup
- incomplete run recovery policy
- event replay support where needed
- improved diagnostics and operator tooling

Tests:
- interrupted run recovery
- stale worktree cleanup
- merge cleanup on failure
- startup consistency checks

## 3. Initial API surface

Do not start with a large API.
Build only what the browser needs for the core flows.

Recommended initial endpoints:
- `POST /projects/open`
- `GET /graph`
- `GET /nodes/{node_id}`
- `POST /nodes/{node_id}/runs/prompt`
- `POST /merges`
- `GET /merges/{node_id}/report`
- `GET /diffs/code`
- `GET /diffs/context`
- `GET /events/stream`
- `POST /runs/{run_id}/cancel`

Keep the transport graph-native.
Avoid container-oriented or session-oriented naming.

## 4. Recommended first runtime adapter

Implement the first adapter as `PiRuntimeAdapter`.

Pi is the best first runtime because it already supports:
- persistent sessions
- session forking
- RPC event streaming
- extensions
- skills
- prompt templates
- compaction hooks
- model/provider routing

However, pi must remain an adapter, not the architecture.

Adapter responsibilities:
- accept input context and workspace
- stream structured events
- provide transcript output
- report terminal status
- emit enough signals for context projection
- capture runtime-specific artifacts without leaking them into the core model

Adapter non-responsibilities:
- node lifecycle decisions
- merge decisions
- graph persistence
- context merge semantics

Follow-on adapters for Claude Code and Codex should be expected, even if implemented later.

## 5. Data migration policy

Pre-1.0 schema iteration is intentionally migration-free.

Until the 1.0 schema baseline:
- local SQLite databases are development artifacts
- schema compatibility is not guaranteed
- contributors may need to delete/recreate local daemon state after schema changes
- SQLAlchemy metadata creation is acceptable for fresh local databases

Before 1.0:
- define the stable schema baseline
- introduce Alembic or an equivalent migration mechanism
- create the initial baseline migration
- document any supported upgrade path from final pre-1.0 development state

This policy is recorded in `docs/adrs/0006-defer-migrations-until-1-0.md`.

## 6. Test strategy by milestone

### By Phase 1
Unit and repository tests should dominate.

### By Phase 3
Integration tests should cover full prompt-to-child-node flow.
They should also validate that the runtime adapter contract is not pi-specific in its normalized outputs.

### By Phase 5
Golden-path and conflict-path merge integration tests are mandatory.

### By Phase 6
Failure, interruption, and recovery tests are mandatory.

## 7. CI quality gates

Every branch should run at least:
- `ruff check`
- `ruff format --check`
- `mypy --strict`
- `pytest --cov`

Do not merge with failing checks.

## 8. Definition of milestone completeness

A phase is complete only when:
- code is implemented
- docs are current
- tests cover the new invariant-bearing behavior
- failure paths are considered
- the resulting API or model remains consistent with the manifesto

## 9. Things not to do early

Avoid these temptations in the first serious implementation cycle:
- multi-user support
- cloud-first orchestration
- premature plugin systems beyond clear adapter boundaries
- runtime-specific product logic in the core application layer
- clever but opaque context compression
- replacing git semantics with home-grown snapshot logic
- giant “temporary” god modules

## 10. What success looks like

The first production-worthy internal milestone is not “feature parity with the prototype.”

It is this:

- a developer can open a repo locally
- create a root node from `HEAD`
- prompt from that node into a child
- watch the child run live
- inspect the child’s code and context
- retry from the same parent into a sibling
- merge two nodes into a new integration node using a common ancestor for both code and context
- understand clean and conflicted outcomes clearly

That is the minimum honest release.
