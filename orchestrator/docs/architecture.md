# Architecture Overview

This document defines the intended architecture of Agents of Chaos.

It should be treated as the implementation reference until superseded by ADRs.

## 1. Scope

Agents of Chaos is a **local-first daemon** that powers a browser-native graph of agent work.

It must support:

- immutable graph nodes
- ephemeral agent runs
- first-class code snapshots
- first-class context snapshots
- code and context diffs
- code and context merges from a common ancestor
- live event streaming to the browser
- pluggable agent runtime adapters

## 2. Core model

### 2.1 Node
A node is the durable unit of work in the graph.

Each node references:
- one code snapshot
- one context snapshot
- zero or one originating run
- one or more parent nodes
- artifacts and derived summaries

Nodes are immutable with respect to code and context.

### 2.2 Run
A run is temporary execution against a source node.

A run:
- starts from a node’s code and context snapshots
- uses a temporary worktree
- streams events while executing
- either produces a new child node or terminates in failure/cancellation

Runs are operational state. Nodes are durable product state.

### 2.3 Code snapshot
A code snapshot is a durable reference to repository state.

Initial implementation guidance:
- represent code snapshots by git commit SHA plus daemon-managed refs
- use worktrees for ephemeral execution sandboxes
- never treat a mutable working directory as the canonical node state

### 2.4 Context snapshot
A context snapshot is a durable, typed representation of branch understanding.

It is not equivalent to a raw transcript.
It is a structured projection derived from provenance and explicitly versioned.

## 3. Architectural invariants

### 3.1 Node immutability
After creation, a node’s code snapshot ID and context snapshot ID must never change.

### 3.2 Shared merge ancestry
Every merge must resolve a common ancestor for:
- code merge
- context merge

The ancestor for context must be lineage-consistent with the node graph.

### 3.3 Durable provenance
The system must preserve:
- run events
- transcripts
- artifact lineage
- snapshot ancestry
- merge reports and conflicts

### 3.4 Browser truthfulness
The browser must be able to reconstruct what happened from durable state and streamed events without relying on hidden mutable backend state.

## 4. Proposed component layout

```text
src/agentsofchaos_orchestrator/
  api/
    app.py
    dependencies.py
    routes/
  application/
    commands/
    queries/
    services/
    transactions/
  domain/
    nodes.py
    runs.py
    context.py
    artifacts.py
    events.py
    errors.py
    enums.py
    ids.py
  infrastructure/
    db/
    git/
    runtime/
    context/
    artifacts/
    logging/
    settings.py
  main.py
```

Exact module names may evolve, but the separation of concerns should remain.

## 5. Storage model

## 5.1 SQLite as the system of record
SQLite is the durable local source of truth.

Store at minimum:
- projects
- nodes
- runs
- code snapshots
- context snapshots
- artifacts
- event records
- merge records

Recommended settings:
- WAL mode
- foreign keys on
- transactional writes
- migration-free schema iteration before 1.0
- an explicit baseline migration before the 1.0 schema is declared stable

## 5.2 Git as code substrate
Git stores code lineage and snapshot content.

Recommended initial strategy:
- use commit SHA as the durable content identity
- maintain daemon-owned refs under `refs/aoc/nodes/<node-id>`
- use temporary worktrees for run execution and merge execution

## 5.3 Daemon-owned working area
Use a dedicated `.aoc/` directory in the managed repository root.

Recommended layout:

```text
.aoc/
  db.sqlite
  artifacts/
  sessions/
  transcripts/
  runs/
  worktrees/
  cache/
```

All daemon-managed state outside the git object database should live here.

## 6. Runtime architecture

### 6.1 Runtime adapters, not runtime lock-in
The daemon must use a runtime adapter layer.

The core graph model must not be coupled to one runtime's concepts, transports, or session internals.

AoC owns the canonical:
- graph
- node lineage
- code snapshots
- context snapshots
- merge semantics
- browser API

Runtimes are execution backends that consume snapshots and return normalized provenance.

### 6.2 Required runtime contract
Every runtime adapter should support at minimum:
- launching a run from a source node snapshot
- streaming normalized events
- accepting runtime-neutral cancellation
- declaring its capabilities explicitly
- final transcript capture
- structured or parseable provenance for context projection

The daemon must not hardcode product logic around one agent implementation.

### 6.3 Runtime capabilities are explicit
Not every runtime will support the same feature set.

The adapter layer should model optional capabilities such as:
- persistent runtime sessions
- session fork
- queued steering / follow-up messages
- runtime-side compaction
- custom tools
- custom skills or prompt resources
- image input
- model switching

This allows the system to support both rich runtimes and thin runtimes without forcing pi semantics onto everything.

### 6.4 Pi is the first rich runtime
Pi is the first implementation target because it already supports:
- persistent sessions
- session forking
- RPC streaming
- extensions
- skills
- prompt templates
- compaction hooks
- provider/model routing

AoC should leverage these capabilities through `PiRuntimeAdapter` and pi-specific context projection code, but must not treat pi as the architecture.

### 6.5 Future runtimes
The design must leave room for adapters such as:
- `PiRuntimeAdapter`
- `ClaudeCodeRuntimeAdapter`
- `CodexRuntimeAdapter`

The graph, context model, and merge semantics must remain stable as those adapters are added.

### 6.6 Runtime-specific provenance vs canonical context
Runtime artifacts are evidence.
Canonical context snapshots are AoC-owned projections.

For example:
- pi sessions, compaction entries, and extension custom entries are runtime provenance
- Claude or Codex transcripts would also be runtime provenance
- the typed AoC context snapshot remains the canonical state used for diffing and merging

### 6.7 Temporary worktrees
Every run should execute in a fresh temporary worktree created from the source node’s code snapshot.

Run flow:
1. create worktree from source commit
2. materialize source context snapshot for the runtime
3. launch runtime adapter
4. stream events
5. if successful, commit changes and create child node
6. if failed, capture artifacts and clean up
7. remove worktree unless explicit debugging retention is enabled

## 7. API architecture

The API is for the browser and local tooling.

### 7.1 Preferred surfaces
- HTTP JSON for commands and queries
- SSE for event streaming
- WebSocket only if necessary for a clearly justified use case

Prompt-run creation should return the created run promptly while execution continues under a supervised background task. The browser observes progress through the event stream and may request cancellation by run id.

### 7.2 API design principles
- graph-native naming
- typed payloads
- no transport of ORM internals
- no leaking infrastructure concepts like “container” or “worker image” into product APIs

Recommended top-level operations:
- create/open project
- create root node
- run prompt from node
- merge nodes
- list graph
- inspect node
- inspect run
- diff nodes
- stream events
- cancel run

## 8. Context architecture

Context is a peer of code, not a derivative afterthought.

The daemon should contain dedicated services for:
- projecting typed context from provenance
- diffing context snapshots
- merging context snapshots from a common ancestor
- generating human-facing handoff summaries from structured context

Projection should be split into:
- runtime-neutral context model and merge logic
- runtime-specific projectors that translate runtime provenance into that model

Examples:
- `PiContextProjector`
- `ClaudeCodeContextProjector`
- `CodexContextProjector`

The canonical context rules are documented in `context-model.md`.

## 9. Merge architecture

A merge operation must produce a new integration node.

### 9.1 Merge inputs
- source node
- target node
- common ancestor node
- source code snapshot
- target code snapshot
- ancestor code snapshot
- source context snapshot
- target context snapshot
- ancestor context snapshot

### 9.2 Merge outputs
- integration code snapshot or code conflict artifact
- integration context snapshot or context conflict artifact
- merge report artifact
- integration node status reflecting merge outcome

### 9.3 Conflict states
Model code conflict and context conflict independently.
A merge result may therefore be:
- ready
- code_conflicted
- context_conflicted
- both_conflicted

### 9.4 Implementation baseline
The first merge implementation resolves the nearest common graph ancestor, verifies that its code snapshot matches git's merge-base, verifies that source and target context snapshots descend from the ancestor context snapshot, performs a no-commit git merge in a temporary worktree, and creates a new `merge` node. Context merge is deterministic and ancestor-based over AoC context snapshots. The implementation records a merge report artifact and emits `merge_node_created`.

Merge reports are retrievable through the API and include source/target/ancestor snapshot ids, changed files, git stdout/stderr, conflicted file paths, conflict marker previews where available, index stage metadata, and context conflict records.

Conflict handling is intentionally conservative. Conflicted merge nodes are durable graph nodes, but richer browser UX and manual conflict resolution remain future work.

## 9.5 Run lifecycle policy

Run status transitions are domain policy, not incidental application-service assignments.

The allowed lifecycle is:
- `queued -> running`
- `queued -> cancelled`
- `running -> succeeded`
- `running -> failed`
- `running -> cancelled`

Cancellation is distinct from failure. Runtime cancellation should produce a cancelled run, not a failed run.

Terminal statuses do not transition further.

Application services should use the run lifecycle policy before persisting status changes.

Active runs are supervised in-process before 1.0. The supervisor owns cancellation tokens and task shutdown. Durable run state remains in SQLite; the supervisor is operational state only and must not become graph truth.

Startup recovery reconciles non-terminal runs left behind by a daemon shutdown or crash. Stale queued runs become cancelled. Stale running runs become failed, because the runtime process and worktree execution are no longer live. Recovery emits normal run lifecycle events with recovery metadata. Startup also removes stale AoC-owned worktree directories and prunes git worktree metadata.

The event outbox has a supervised background dispatcher. Inline dispatch remains an optimization for low-latency updates, but the durable outbox is the recovery boundary for events that were recorded but not published.

Cancellation preserves runtime evidence when the adapter can provide it. A cancelled pi run may still record a partial transcript and session artifact; those artifacts are provenance, not a child node.

## 10. Event model

Persist an append-only event log for:
- run lifecycle events
- node creation
- merge lifecycle
- conflict detection
- artifact creation
- cleanup / reconciliation events

The event log serves three purposes:
- live browser streaming
- debugging and observability
- replay and postmortem analysis

Durable state changes that produce events should write the domain state, event record, and outbox record in one transaction where practical. Live delivery is handled separately from durable event creation. Pre-1.0 may still publish inline after commit, but durable publishing must go through an explicit outbox dispatcher boundary so the system can converge on background dispatch without changing event semantics.

## 11. Recommended technology choices

### 11.1 Application stack
- FastAPI
- Pydantic 2
- SQLAlchemy 2.x
- SQLite + Alembic
- AnyIO / asyncio
- Ruff
- mypy
- pytest + pytest-asyncio + pytest-cov

### 11.2 Git integration
Start with `subprocess.run()` using argument lists, wrapped in a typed git service.

Reason:
- maximum fidelity to actual git behavior
- fewer surprises than partial library abstractions
- easier parity with command-line workflows

Do not shell out through interpolated shell strings.

## 11.5 Application transaction boundary

Application services should coordinate durable writes through an explicit unit-of-work boundary rather than scattering transaction management across unrelated methods.

The unit-of-work boundary exists to make these operations coherent:
- repository access
- transaction commit/rollback
- event record creation
- outbox record creation
- future recovery/reconciliation

## 12. Implementation order

Recommended sequence:

1. project opening and daemon-owned local state
2. graph persistence schema
3. root node creation from `HEAD`
4. runtime adapter interface
5. prompt run to child node flow
6. transcript and event persistence
7. typed context projection
8. context diff and inspection
9. merge flow with common-ancestor resolution
10. context merge and conflict handling
11. reconciliation and cleanup hardening

## 13. Non-goals for the initial release

Not in the first serious implementation pass:
- multi-user collaboration
- distributed orchestration
- hosted cloud control plane
- remote sandbox fleet management
- CRDT-based shared editing
- clever context compression schemes before correctness is proven

## 14. Success criteria

The architecture is successful when the daemon can reliably support this user story:

1. open a local repository
2. create a root node from current `HEAD`
3. run a prompt from that node and see a child node stream live output
4. retry from the same parent and compare siblings
5. inspect code and context diffs between nodes
6. merge two nodes into an integration node from a common ancestor
7. inspect both code merge and context merge results, including conflicts

If the architecture cannot support that cleanly, it is not the right architecture.
