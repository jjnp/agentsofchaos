# ADR 0008: Treat conflicted merge nodes as immutable conflicted workspace snapshots

- Status: Accepted
- Date: 2026-04-25

## Context

Agents of Chaos merge nodes reconcile both code and context from a common ancestor.

A merge may be clean, code-conflicted, context-conflicted, or both-conflicted. The first merge implementation records conflicted merge nodes as durable graph nodes and writes a merge report artifact.

For code conflicts, git leaves conflict markers and unmerged index stages in the merge worktree. The orchestrator can either:

1. refuse to create a node until conflicts are resolved, or
2. capture the conflicted workspace as a durable graph node.

Refusing to create a node hides useful provenance and makes the browser unable to represent the merge attempt as a first-class graph event. Capturing the workspace preserves exactly what happened, but risks confusing a conflicted snapshot with a clean integration result.

The same distinction exists for context: a context-conflicted merge may produce a snapshot candidate containing conflicted context items, but that candidate is not a clean reconciled branch understanding.

## Decision

Conflicted merge attempts **do create immutable graph nodes**.

A merge node's status is the immutable outcome of the merge attempt:

- `ready`
- `code_conflicted`
- `context_conflicted`
- `both_conflicted`

A code snapshot attached to a code-conflicted merge node is a **conflicted workspace snapshot**, not a clean integration snapshot. It may contain conflict markers and is not guaranteed to build or run.

A context snapshot attached to a context-conflicted merge node is a **conflicted context candidate**, not clean reconciled context. It may contain conflicted context items and must preserve conflict metadata.

Conflict resolution must not silently reinterpret the original conflicted node as clean. The default resolution policy is:

> create a successor node that records the resolved code/context and points back to the conflicted merge attempt through normal graph lineage and provenance.

The original conflicted node remains durable evidence of the merge attempt.

## Implementation guidance

Merge responses and reports should distinguish snapshot roles explicitly.

For code snapshots:

- `integration` means the code merge was clean and the snapshot represents the integrated code result.
- `conflicted_workspace` means the snapshot captures a conflicted merge workspace and may include conflict markers.

For context snapshots:

- `merged_context` means the context merge was clean.
- `conflicted_context_candidate` means the context merge produced conflicts and the snapshot is a candidate containing conflict state.

Merge reports should include:

- node status
- code snapshot role
- context snapshot role
- resolution policy
- conflict marker details where available
- context conflict records

Future conflict resolution APIs should create successor resolution nodes unless a later ADR deliberately changes that policy.

## Consequences

### Positive

- every merge attempt is graph-visible and durable
- conflict evidence is preserved precisely
- the browser can inspect conflicted workspaces and reports
- node immutability remains simple: the conflicted node is not rewritten into a clean node
- resolution becomes auditable as a separate graph event

### Negative

- not every code snapshot is buildable or semantically integrated
- consumers must respect the snapshot role and node status before treating a snapshot as runnable
- conflict resolution requires additional backend/API work
- docs and UI must make conflicted workspace semantics clear

## Follow-up work

- Expand the first-cut typed conflict/report domain models into resolution APIs.
- Add conflict resolution APIs.
- Add validation that resolved code snapshots do not contain unresolved conflict markers.
- Add context conflict resolution decisions with provenance.
- Add browser UX that clearly separates conflicted workspace snapshots from clean integration snapshots.
