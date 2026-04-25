# ADR 0009: Resolve conflicted merges by creating successor nodes

- Status: Accepted
- Date: 2026-04-25

## Context

ADR 0008 defines conflicted merge attempts as immutable graph nodes. A conflicted merge node may contain:

- a code snapshot role of `conflicted_workspace`
- a context snapshot role of `conflicted_context_candidate`
- a node status of `code_conflicted`, `context_conflicted`, or `both_conflicted`

This preserves the merge attempt as durable evidence, but it does not by itself define how an agent run turns that attempt into a clean result.

The system needs a resolution model that preserves immutability, provenance, and graph truthfulness.

## Decision

Conflict resolution must be **agent-driven** and must create a **successor node** rather than mutating the original conflicted merge node into a clean node.

Resolution is not a manual user-edit workflow. The user may provide intent, constraints, or review feedback as a prompt, but the actual resolution work is performed by a runtime adapter in an ephemeral run from the conflicted merge node.

The original conflicted merge node remains the immutable record of the failed/conflicted integration attempt.

The successor node represents the resolved result. It has its own:

- code snapshot
- context snapshot
- node status
- artifact provenance
- event records
- resolution report artifact

The successor's graph parentage should include the conflicted merge node so the graph visibly represents:

```text
source ─┐
        ├─ conflicted merge ── resolution successor
target ─┘
```

## Resolution run model

Resolution is a specialized prompt run.

A resolution run:

1. starts from the conflicted merge node's code and context snapshots
2. creates a fresh temporary worktree from the conflicted workspace snapshot
3. injects the merge report, conflict details, source/target/ancestor metadata, and current context into the runtime prompt
4. asks the selected runtime adapter to resolve both code and context conflicts according to user intent and AoC policy
5. captures runtime events, transcript/session artifacts, and resolution evidence
6. validates the resulting workspace and context projection
7. creates a successor node only if validation succeeds

The user-facing command should therefore look like a prompt, not a manual file-submission API. For example, a future API may be shaped as:

```http
POST /projects/{project_id}/merges/{node_id}/resolution-runs/prompt
```

with a request body containing natural-language resolution intent such as:

```json
{ "prompt": "Resolve the merge by preserving the SQLite WAL decision and keeping the new API route from the target branch." }
```

The backend may provide default resolution instructions when the user supplies no extra intent, but resolution still runs through an agent runtime.

### Code resolution

A code resolution produces a new clean code snapshot from the conflicted workspace after the agent edits the resolution worktree.

Before successor-node finalization, the backend must validate:

- no git unmerged index entries remain
- no unresolved conflict markers remain in resolved files, unless explicitly waived by a future ADR
- the resolved tree can be committed

The backend should not accept direct user-submitted replacement contents as the primary resolution mechanism. If a future escape hatch permits manual patch upload, it must be documented separately and must still produce provenance explaining why an agent-run resolution was bypassed.

### Context resolution

A context resolution produces a clean context snapshot from a conflicted context candidate by projecting the agent's resolution evidence into AoC context.

The agent may choose, synthesize, mark resolved, or mark superseded context items, but AoC must record those decisions as structured provenance.

Every context resolution decision must preserve provenance explaining:

- which conflict it resolved
- which source/target/ancestor item it considered
- whether the resolved item was selected or synthesized
- which runtime/run produced the decision
- which artifacts or transcript/session entries support the decision

## Successor node kind

The preferred long-term graph kind is `resolution` because a conflict-resolution successor is semantically distinct from the original merge attempt.

Before adding that kind to the schema/UI, a short-lived implementation may represent resolution successors as `merge` nodes with an explicit resolution report artifact. If this shortcut is taken, it must be removed before 1.0 or documented in a follow-up ADR.

## Required artifacts

A finalized resolution must record a resolution report artifact containing:

- conflicted merge node id
- successor node id
- original source/target/ancestor node ids
- original merge report artifact id or path if known
- resolution prompt and runtime kind
- resolution run id
- code validation result
- context resolution decisions projected from runtime evidence
- resulting code snapshot id
- resulting context snapshot id
- resulting git ref and commit sha

The report is evidence. The successor node's snapshots remain canonical state.

## Required events

The system should emit durable events for:

- resolution run created
- resolution run started
- resolution successor created
- resolution run failed or cancelled

Resolution reuses the normal run lifecycle where possible. The successor-created event records that a resolution run produced a durable node.

## Consequences

### Positive

- preserves node immutability
- preserves the conflicted merge as inspectable evidence
- makes conflict resolution auditable
- gives the browser a truthful graph story
- keeps resolution consistent with prompt-driven AoC workflows
- captures agent reasoning and runtime provenance for the resolution

### Negative

- graph gains another node for every resolved conflict
- resolution requires runtime execution even for simple conflicts
- resolution requires additional APIs and artifacts
- UI must distinguish conflicted merge nodes from resolution successors
- implementation must validate both git state and context decisions
- manual editor workflows become secondary escape hatches rather than the main path

## Follow-up work

- Add a `resolution` node kind or document a temporary `merge`-kind fallback.
- Add typed resolution prompt-run request/response models.
- Add resolution report domain models.
- Add agent-driven resolution run API.
- Add runtime prompt/context injection for merge conflict evidence.
- Add validation for unresolved code conflict markers and unmerged git index entries.
- Add browser UX for conflict inspection and successor-node creation.
