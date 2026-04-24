# Context Model

This document defines the first-class context model for Agents of Chaos v2.

## 1. Why this exists

Most agent systems treat context as one of the following:
- an opaque transcript
- a hidden model session
- a markdown summary
- a pile of tool logs

That is insufficient for v2.

In Agents of Chaos v2, context must be:
- durable
- inspectable
- typed
- comparable
- mergeable
- grounded in provenance

## 2. Design principles

### 2.1 Context is a peer of code
Every node has:
- one code snapshot
- one context snapshot

Neither is secondary.

### 2.2 Transcript is evidence, not the model
Raw transcript and tool provenance are important, but they are not the canonical context model.

The canonical model is a structured context snapshot derived from that evidence.

### 2.3 Context must support ancestor-based merge
Context merging must be a real three-way reconciliation from a common ancestor, analogous to code merge semantics.

### 2.4 Provenance is mandatory
Context items must know where they came from:
- node
- run
- transcript entry
- artifact citation when available

## 3. Context snapshot shape

Initial implementation guidance:

```python
@dataclass(frozen=True)
class ContextSnapshot:
    id: ContextSnapshotId
    parent_ids: tuple[ContextSnapshotId, ...]
    transcript_ref: TranscriptRef | None
    summary: str
    goals: tuple[ContextItem, ...]
    constraints: tuple[ContextItem, ...]
    decisions: tuple[ContextItem, ...]
    assumptions: tuple[ContextItem, ...]
    open_questions: tuple[ContextItem, ...]
    todos: tuple[ContextItem, ...]
    risks: tuple[ContextItem, ...]
    handoff_notes: tuple[ContextItem, ...]
    read_files: tuple[FileRef, ...]
    touched_files: tuple[FileRef, ...]
    symbols: tuple[SymbolRef, ...]
    merge_metadata: MergeMetadata | None
    created_at: datetime
```

Exact field names may evolve, but the intent should remain.

## 4. Typed context items

A context item should not be only free text.

Initial guidance:

```python
@dataclass(frozen=True)
class ContextItem:
    id: ContextItemId
    text: str
    status: ContextItemStatus
    provenance_node_id: NodeId
    provenance_run_id: RunId | None
    citations: tuple[ArtifactRef, ...]
```

Recommended status values:
- `active`
- `resolved`
- `superseded`
- `conflicted`

## 5. Canonical context sections

The initial typed model should include at least:

- `goals`
- `constraints`
- `decisions`
- `assumptions`
- `open_questions`
- `todos`
- `risks`
- `handoff_notes`
- `read_files`
- `touched_files`
- `symbols`

These are intentionally practical and implementation-oriented.

## 6. Provenance inputs

A context snapshot is derived from provenance such as:
- user prompts
- assistant messages
- tool calls
- tool results
- file reads and writes
- explicit artifacts
- merge reports
- prior context snapshots
- runtime-specific transcript and session artifacts

The implementation should preserve raw provenance separately from the structured snapshot.

## 6.1 Runtime-specific projectors

Context projection must support multiple runtimes.

The canonical context schema remains AoC-owned and runtime-independent.
Runtime-specific projectors are responsible for translating runtime evidence into that schema.

Examples:
- pi session JSONL + extension custom entries -> `PiContextProjector`
- Claude Code transcripts -> `ClaudeCodeContextProjector`
- Codex traces or transcripts -> `CodexContextProjector`

This separation is required so nodes produced by different runtimes remain comparable and mergeable.

## 7. Context projection

Each run should produce:

1. a raw transcript / event log
2. a derived context projection
3. a final stored context snapshot for the child node

Projection guidance:
- deterministic extraction where possible
- model-assisted summarization only where needed
- explicit provenance attachment
- no hidden mutation of prior snapshots

## 8. Diffing context

The UI must be able to compare context snapshots between nodes.

At minimum, a context diff should identify:
- items added
- items removed
- items marked resolved
- items marked superseded
- summary changes
- newly read files
- newly touched files
- newly observed risks

The diff logic should be explicit and testable.

## 9. Merge semantics

## 9.1 Hard rule
Context merges must reconcile from a common ancestor.

Given source node `S` and target node `T`, the system must resolve a common ancestor `A` and merge:
- `A.context`
- `S.context`
- `T.context`

There is no supported lineage-free merge mode for canonical context.

## 9.2 Merge inputs
A context merge takes:
- ancestor context snapshot
- source context snapshot
- target context snapshot
- merge strategy version

## 9.3 Merge outputs
A context merge produces:
- merged context snapshot candidate
- zero or more context conflicts
- merge report artifact

## 10. Section merge strategy

Different sections merge differently.

### 10.1 Deterministic union sections
These should merge structurally where practical:
- `read_files`
- `touched_files`
- `symbols`
- some `todos`
- some `risks`

Preferred behavior:
- union with stable deduplication
- preserve provenance
- keep item ordering deterministic

### 10.2 Semantic reconciliation sections
These require true three-way reconciliation:
- `goals`
- `constraints`
- `decisions`
- `assumptions`
- `open_questions`
- `handoff_notes`
- `summary`

The merge engine should determine:
- what was inherited unchanged from ancestor
- what source changed since ancestor
- what target changed since ancestor
- whether the changes are compatible
- whether a conflict should be raised

### 10.3 Conflict-prone sections
Conflicts should be explicit when branches disagree materially.

Examples:
- opposite architectural decisions
- incompatible constraints
- contradictory assumptions
- one branch resolving an issue in a way the other branch rejects

## 11. Context conflicts

Context conflict is a first-class outcome.

A merge may be:
- code clean + context conflicted
- code conflicted + context clean
- both conflicted
- both clean

Recommended conflict record shape:

```python
@dataclass(frozen=True)
class ContextConflict:
    id: ContextConflictId
    section: ContextSection
    ancestor_items: tuple[ContextItem, ...]
    source_items: tuple[ContextItem, ...]
    target_items: tuple[ContextItem, ...]
    explanation: str
    severity: ConflictSeverity
```

## 12. Merge reports

Every context merge should emit durable artifacts such as:
- `context-merge-report.json`
- `context-merge-summary.md`
- `context-conflicts.json`

These should capture:
- ancestor/source/target snapshot IDs
- merge strategy version
- merged sections
- conflicts
- any model-assisted reconciliation notes

## 12.1 Cross-runtime requirement

The context model must be able to represent branches created by different runtimes without changing the schema.

That means:
- runtime transcripts are evidence
- canonical context items are AoC projections
- context merges operate on AoC snapshots, not on raw runtime transcript formats

## 13. Model usage policy

LLMs may assist context projection and context merge, but they must not be the entire mechanism.

Preferred rule:
- deterministic outer structure
- model-assisted inner reconciliation where necessary
- provenance retained
- conflicts preserved instead of silently flattened

Forbidden shortcut:
- “concatenate transcripts and summarize them” as the canonical merge strategy

## 14. Initial implementation guidance

Start with a minimal but honest model.

### Phase 1
Implement typed snapshots with these sections:
- goals
- decisions
- open_questions
- handoff_notes
- read_files
- touched_files
- risks

### Phase 2
Add:
- constraints
- assumptions
- todos
- symbols
- richer provenance links

### Phase 3
Add smarter deterministic matching and model-assisted semantic reconciliation.

## 15. Quality bar

The context model is only acceptable if it is:
- representable as typed Python domain objects
- persistable without lossy hand-waving
- diffable in tests
- mergeable from a common ancestor in tests
- inspectable in the UI
- understandable by a human reading the artifacts

If it cannot meet those standards, it is not yet first-class.
