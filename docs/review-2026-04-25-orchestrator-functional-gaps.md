# Orchestrator functional gap review — 2026-04-25

## Summary

The Python orchestrator is **not functionally done** yet.

It is now a substantial alpha-quality backend foundation for Agents of Chaos:

- local FastAPI daemon
- SQLite durable state
- immutable node records
- code snapshots
- context snapshots
- run records
- runtime adapter boundary
- no-op runtime
- pi runtime adapter over RPC
- supervised background prompt runs
- run cancellation request flow
- runtime events
- durable event records
- event outbox
- SSE event streaming
- artifacts for transcripts/sessions/reports
- node code diffs
- prompt-run child node creation
- common-ancestor merge service
- git worktree code merge
- deterministic context merge service
- merge report artifacts
- merge report retrieval
- startup recovery for interrupted runs
- stale worktree cleanup

This is a strong foundation, but it is not yet the complete AoC orchestrator. The remaining gaps are functional/product gaps, not just test or formatting gaps.

## Current status call

Call the orchestrator:

> Functional foundation / alpha backend.

Do **not** call it done yet.

It can support the golden-path graph workflow:

1. open a repository
2. create a root node
3. run a prompt through a runtime adapter
4. create a child node
5. inspect run events, snapshots, and diffs
6. create sibling branches
7. merge branches
8. inspect merge report artifacts

But the hard product edges are still incomplete:

- merge conflict resolution
- mature context projection
- mature context merge semantics
- durable cancellation semantics
- fully correct event/outbox delivery semantics
- state integrity lifecycle
- runtime ecosystem beyond pi
- operational health and recovery

## Functional gaps

### 1. Merge conflict resolution is not implemented

The backend can produce conflicted merge nodes with statuses:

- `code_conflicted`
- `context_conflicted`
- `both_conflicted`

But there is no backend flow to resolve them.

Missing capabilities:

- inspect conflicts through first-class typed models, not only report JSON
- submit resolved code conflict contents
- submit resolved context conflict decisions
- validate that code conflict markers are gone
- finalize a conflicted merge into a clean integration result
- decide whether resolution mutates the conflicted merge node status or creates a successor resolution node
- preserve audit/provenance for conflict resolution

Until this exists, conflicted merge nodes are durable evidence, but not an actionable merge workflow.

### 2. Conflicted code merge semantics are now explicit, but resolution is still missing

ADR 0008 records the product decision: a `code_conflicted` merge node may point at a code snapshot containing conflict markers. That snapshot is a durable `conflicted_workspace`, not a clean `integration` snapshot and not guaranteed to build or run.

ADR 0008 defines the default resolution policy as `successor_node`, and ADR 0009 expands that policy: resolving conflicts should create a successor node with its own code/context snapshots and provenance rather than silently rewriting the original conflicted node.

Remaining gaps:

- backend resolution flow
- resolved-code validation
- context-resolution decision capture
- UI distinction between conflicted workspace snapshots and clean integration snapshots

### 3. Context merge is structurally present but still shallow

The context merge engine is deterministic and ancestor-based, but still minimal.

Current behavior:

- merges context item tuples by item UUID
- detects conflicts when the same item changes differently on both sides
- appends a merge handoff note
- unions file references and symbol references

Missing capabilities:

- typed context conflict models instead of loose dictionaries
- section-specific merge semantics
- semantic duplicate detection
- explicit handling for resolved/superseded items
- stronger provenance for every merged/changed/conflicted item
- context conflict resolution flow
- richer report structure explaining inherited/source/target changes

The boundary is correct, but the semantics are not mature yet.

### 4. Runtime evidence projection is preliminary

Canonical context projection from runtime evidence is still simple.

Current projection mostly records:

- prompt as a goal
- runtime summary as snapshot summary
- touched files from git diff
- a handoff note

Missing capabilities:

- extract decisions
- extract assumptions
- extract risks
- extract todos
- extract read files from runtime events/session evidence
- extract symbols
- cite artifacts/events precisely
- project pi session entries and compaction output into AoC context
- runtime-specific projector boundary, especially `PiContextProjector`

This is a major gap because AoC's core claim is not just code branching; it is code **plus context** branching and merging.

### 5. Run cancellation is operational, not durable

Cancellation currently works through the in-memory active-run supervisor and runtime cancellation tokens.

Missing capabilities:

- persisted cancellation requests
- cancellation after daemon restart
- clear command semantics such as `202 Accepted`
- status distinction between cancellation requested, acknowledged, and completed
- cancellation reason
- active-run status API
- guaranteed partial artifact preservation across adapters

Current cancellation is useful for live runs, but not yet a full durable run-control model.

### 6. Background supervision is basic

The orchestrator has a run supervisor and an outbox worker, but not a complete supervised daemon runtime.

Missing capabilities:

- worker health visibility
- active run listing
- task crash/restart policy
- graceful shutdown deadlines
- metrics or diagnostic endpoint
- per-project concurrency controls
- startup reconciliation for partially materialized merges

The current supervisor is a good first implementation, not a full operational substrate.

### 7. Event/outbox delivery semantics need tightening

The outbox gives the system a durable event boundary, but current live delivery semantics are not yet ideal.

Current risk:

- if an event is marked published before live publish completes, a crash between those operations can lose live delivery

This may be acceptable short-term because clients can reload historical events from SQLite, but it should be made explicit and improved.

Missing capabilities:

- explicit event delivery semantics
- SSE `Last-Event-ID` support
- replay cursor API
- idempotent client event handling contract
- clear distinction between recorded, claimed, and live-published states

### 8. API surface is not graph-complete

Implemented APIs cover the golden path, but important graph/backend surfaces are missing.

Missing APIs include:

- list artifacts by project/node/run
- get artifact metadata
- safe artifact content retrieval
- inspect active runs
- inspect runtime adapter/capabilities
- code diff between arbitrary nodes
- context diff between arbitrary nodes
- compare two nodes
- retry run / sibling run semantics
- fork/import/manual node creation
- project close/remove
- event replay cursor
- merge conflict resolution

### 9. Runtime adapter ecosystem is incomplete

Current runtime adapters:

- no-op runtime
- pi runtime

Planned but not implemented:

- Claude Code adapter
- Codex adapter
- custom adapter plugin/config mechanism
- runtime capability API
- per-run model/provider selection
- adapter health checks
- adapter-specific context projectors

This is acceptable for pi-first development, but not complete for the runtime-agnostic product goal.

### 10. Pi integration is useful but not final

The pi RPC adapter is real and useful, but the deeper AoC/pi bridge is not implemented.

Missing capabilities:

- AoC pi extension package
- graph-aware pi tools
- structured provenance emitted from pi
- custom compaction/handoff integration
- durable mapping from pi session evidence to AoC context items
- richer pi session lifecycle controls
- robust handling of pi auth/provider/model failures
- runtime stderr artifact capture
- raw runtime event log artifact capture

The current adapter treats pi as a capable runtime, but not yet as a deeply integrated graph collaborator.

### 11. Snapshot immutability is mostly policy, not strongly enforced

The implementation generally respects immutability by creating new snapshots and nodes.

Still missing:

- stronger repository/API restrictions preventing snapshot mutation
- explicit immutability checks for node code/context snapshot IDs
- clear separation between immutable graph state and mutable display metadata
- integrity checks that detect illegal mutation

The invariant is respected by convention today. It should become enforceable.

### 12. Local state lifecycle is incomplete

SQLite, git refs, and `.aoc` artifacts are present, but the full state lifecycle is not done.

Missing capabilities:

- 1.0 schema baseline and migration plan
- state integrity checker
- repair tool
- orphan artifact cleanup
- orphan git ref cleanup
- stronger stale worktree cleanup policy
- project export/import
- backup/restore guidance
- schema version metadata

Pre-1.0 can avoid migrations, but a done orchestrator needs a durable state story.

### 13. Error handling and failure policy are uneven

Domain errors and API handlers exist, but failure semantics still need refinement.

Missing or unclear:

- precise error distinctions for merge conflict vs invalid ancestry vs missing report
- runtime-specific error classification
- consistent API error response model
- artifact failure policy
- event publish failure policy
- cleanup policy for partial merge failure
- user-visible recovery hints

### 14. Security and filesystem boundaries need tightening

The code generally uses subprocess argument arrays, which is good.

Still missing or unclear:

- strict path containment for artifact/report reads
- safe artifact content exposure policy
- prevention of daemon-owned state overlap with repository content
- repository allowlist or trust policy
- handling malicious filenames/content in diff and report previews
- redaction policy for runtime transcripts/session files

Local-first reduces risk but does not remove it.

## Recommended functional priorities

Do not add broad new product surface before stabilizing these areas.

### Priority 1 — implement merge conflict resolution

ADR 0008 has decided conflicted merge semantics, and ADR 0009 has decided the successor-node resolution model. Resolution must be agent-driven: the user supplies prompt intent, and a runtime adapter performs the code/context resolution in an ephemeral resolution run.

First-cut backend pieces now exist for an agent-driven resolution prompt-run API, conflict-evidence prompt injection, post-run code validation, successor node creation, and a resolution report artifact. Remaining backend pieces:

- API/integration coverage for the resolution-run endpoint
- richer typed resolution report models
- context-resolution projection from runtime evidence
- structured resolution-decision provenance
- runtime-specific resolution quality improvements, especially for pi

### Priority 2 — mature typed merge reports

First-cut typed merge report/conflict domain models now exist. Remaining backend pieces:

- use typed report models throughout resolution APIs
- expose stable typed report DTOs instead of generic report dictionaries
- add richer context conflict records with ancestor/source/target item groups
- add typed resolution result reports
- remove remaining loose dictionaries from core merge state

### Priority 3 — build real context projection

Needed backend pieces:

- `PiContextProjector`
- typed extraction of decisions/todos/risks/files/symbols
- artifact citations
- projection reports
- deterministic fallback behavior

### Priority 4 — add context diff

Needed backend pieces:

- context diff between node and parent
- context diff between arbitrary nodes
- section-level changes
- item-level provenance
- conflict-friendly output

### Priority 5 — make cancellation durable

Needed backend pieces:

- persisted cancellation command/request
- active run inspection
- cancellation lifecycle/status
- startup recovery for cancellation-in-progress

### Priority 6 — add artifact APIs

Needed backend pieces:

- list artifacts by project/node/run
- get artifact metadata
- safe content retrieval for text/json artifacts
- artifact redaction policy

### Priority 7 — clarify outbox/event semantics

Needed backend pieces:

- replay cursor
- SSE `Last-Event-ID`
- explicit recorded/claimed/published state model
- idempotent client contract

### Priority 8 — add state integrity tooling

Needed backend pieces:

- verify projects/nodes/snapshots/runs/artifacts/git refs
- detect orphaned worktrees/artifacts/refs
- repair or report actionable issues

## Bottom line

The orchestrator is on the right architectural track and supports the basic graph workflow. It should be treated as an alpha backend foundation, not a complete orchestrator.

The next milestone should be functional hardening around merges, context, cancellation, events, artifacts, and state integrity rather than adding unrelated new features.
