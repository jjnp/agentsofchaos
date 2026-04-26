# Continuation guidance — 2026-04-25

This document is a handoff note for continuing work after conversation compaction.

## Active implementation path

The active orchestrator implementation is:

```text
orchestrator/
```

The Python package is:

```text
agentsofchaos_orchestrator
```

Do **not** continue work in the old `apps/orchestrator-v2/` path. The repo has been consolidated so the sanctioned backend path is now `orchestrator/`.

## Product invariants to preserve

The orchestrator exists to implement Agents of Chaos as a graph-native local daemon.

Non-negotiables:

- the graph is primary
- nodes are immutable
- runs are ephemeral
- every node has a code snapshot and a context snapshot
- code merges require a common ancestor
- context merges require a common ancestor
- runtime sessions/transcripts are evidence, not canonical state
- pi is the first rich runtime adapter, not the architecture
- local SQLite/git/artifacts are canonical daemon state

If implementation pressure conflicts with these invariants, change the implementation, not the invariants.

## Current functional state

The orchestrator currently has working alpha implementations for:

- project open with automatic root node creation
- idempotent explicit root-node endpoint for legacy/manual callers
- graph query
- node query
- code snapshot query
- context snapshot query
- node code diff
- prompt runs
- background-supervised prompt execution
- run cancellation request flow
- no-op runtime adapter
- pi runtime adapter over RPC
- runtime event capture
- transcript/session artifact recording
- event records
- outbox records
- SSE event stream
- startup recovery for interrupted queued/running runs
- stale AoC worktree cleanup
- merge nodes
- merge report artifact creation
- merge report retrieval
- deterministic ancestor-based context merge first cut
- agent-driven merge resolution runs
- immutable resolution successor nodes
- typed merge and resolution report models
- resolution report artifacts with merge-report, runtime-artifact, and context-decision provenance

The backend can support a golden-path demo, but it is **not done**. Treat it as an alpha foundation.

Read before changing functionality:

- `docs/review-2026-04-25-orchestrator-functional-gaps.md`
- `docs/architecture.md`
- `docs/context-model.md`
- `docs/runtime-adapters.md`
- `docs/implementation-plan.md`
- `orchestrator/AGENT.md`

## Current validation reality

A `uv` venv exists under:

```text
orchestrator/.venv
```

It was recreated on 2026-04-25 because the old venv had stale console-script shebangs pointing to `apps/orchestrator-v2/.venv`.

Recommended validation commands from repo root:

```bash
cd orchestrator
uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
MYPYPATH=src:. uv run mypy --explicit-package-bases src tests
uv run python -m compileall src tests
```

At the time of this note:

```text
uv run pytest -q
```

passes:

```text
55 passed
```

`tests/` is now a package, so plain `uv run pytest` works without `PYTHONPATH=.`.
Ruff and mypy are clean for the active backend tree:

```bash
uv run ruff check src tests
MYPYPATH=src:. uv run mypy --explicit-package-bases src tests
```

## Important repository status note

At the time this guide was written, `git status --short` showed unrelated frontend work plus an untracked lockfile:

```text
 M frontend/package-lock.json
 M frontend/package.json
?? frontend/playwright.config.ts
?? frontend/tests/
?? orchestrator/uv.lock
```

`orchestrator/uv.lock` was created by `uv sync`. Decide whether to commit it as part of dependency reproducibility. Do not assume it was intentionally ignored.

`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, and `.venv` may exist locally and should not be treated as source work.

## Functional gaps that matter most

The orchestrator is not complete until these are addressed.

### 1. Merge conflict resolution

Merges can produce conflicted merge nodes, and the backend now has an agent-driven successor-node resolution workflow.

Implemented:

- typed conflict and report models for merge/resolution artifacts
- agent-driven resolution prompt-run API
- runtime prompt/context injection for merge conflict evidence
- code validation/finalization after the agent edits the worktree
- initial context-resolution projection from runtime decisions
- provenance for resolution decisions
- immutable successor-node creation
- API coverage for success, non-merge rejection, non-conflicted merge rejection, missing/invalid merge reports, residual conflict markers, unmerged index entries, and runtime failures

Still needed:

- deeper semantic context-resolution projection from runtime evidence
- unambiguous UI affordances for browsing linked resolution evidence

### 2. Conflicted code snapshot semantics

ADR 0008 now decides this: conflicted merge attempts create immutable graph nodes. A code-conflicted merge node's code snapshot is a `conflicted_workspace`, not a clean `integration` snapshot, and it may contain conflict markers. A context-conflicted merge node's context snapshot is a `conflicted_context_candidate`, not clean reconciled context.

The default resolution policy is `successor_node`: resolving conflicts should create a successor node with its own code/context snapshots and provenance rather than silently rewriting the original conflicted merge node. ADR 0009 defines this successor-node resolution model.

Remaining work:

- harden the first-cut agent-driven successor resolution run flow
- add API/integration coverage for the resolution-run endpoint
- deepen context-resolution projection from runtime evidence
- preserve structured resolution decisions as provenance
- make the UI clearly distinguish conflicted workspace snapshots from clean integrations

### 3. Context projection maturity

Current context projection is preliminary.

Needed:

- `PiContextProjector`
- extraction of decisions/todos/risks/assumptions/read files/symbols
- citations to artifacts/events/session evidence
- projection report artifacts

### 4. Context merge maturity

Current context merge is deterministic but shallow.

Needed:

- typed context conflict records instead of loose dicts
- section-specific semantics
- duplicate/superseded/resolved item handling
- context conflict resolution
- richer merge reports

### 5. Durable cancellation

Cancellation currently works for active in-memory runs.

Needed:

- persisted cancellation requests
- active-run inspection
- requested/acknowledged/completed cancellation states
- startup behavior for cancellation in progress

### 6. Event/outbox semantics

The outbox exists, but live delivery semantics need tightening.

Known concern:

- marking an event published before live publish can lose live delivery on a crash between those operations

Needed:

- explicit recorded/claimed/published model or replay-first contract
- SSE `Last-Event-ID`
- event replay cursor
- idempotent client handling contract

### 7. Artifact APIs

Artifacts are persisted but not fully surfaced.

Needed:

- list artifacts by project/node/run
- get artifact metadata
- safe text/json content retrieval
- redaction/content policy

### 8. State integrity lifecycle

Needed before calling local-first storage mature:

- integrity checker
- orphan artifact/ref/worktree detection
- repair/report tool
- 1.0 schema baseline and migration plan
- backup/export guidance

## Suggested next backend priorities

Do not broaden features randomly. Recommended sequence:

1. Harden the first-cut backend merge conflict resolution prompt-run flow.
2. Mature the first-cut typed conflict/report domain models into structured resolution reports.
3. Build `PiContextProjector` and projection report artifacts.
4. Add context diff API.
5. Make cancellation durable and inspectable.
6. Add artifact listing/metadata/content APIs.
7. Tighten outbox replay semantics.
8. Add state integrity checks.
9. Then clean ruff/mypy baselines.

## Files worth reading first

Backend facade and app:

- `orchestrator/src/agentsofchaos_orchestrator/application/services.py`
- `orchestrator/src/agentsofchaos_orchestrator/api/app.py`
- `orchestrator/src/agentsofchaos_orchestrator/api/routes/projects.py`

Domain:

- `orchestrator/src/agentsofchaos_orchestrator/domain/models.py`
- `orchestrator/src/agentsofchaos_orchestrator/domain/enums.py`
- `orchestrator/src/agentsofchaos_orchestrator/domain/run_policy.py`

Runs:

- `orchestrator/src/agentsofchaos_orchestrator/application/runs.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/run_state.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/supervisor.py`

Merges/context:

- `orchestrator/src/agentsofchaos_orchestrator/application/merges.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/context_merge.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/context_projection.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/diffs.py`

Persistence/events:

- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/orm.py`
- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/repositories.py`
- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/unit_of_work.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/eventing.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/outbox.py`
- `orchestrator/src/agentsofchaos_orchestrator/application/outbox_worker.py`

Runtime:

- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/runtime/base.py`
- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/runtime/noop.py`
- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/runtime/pi/adapter.py`
- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/runtime/pi/rpc_client.py`

Git:

- `orchestrator/src/agentsofchaos_orchestrator/infrastructure/git_service.py`

Tests that describe intended behavior:

- `orchestrator/tests/test_prompt_run.py`
- `orchestrator/tests/test_merge_flow.py`
- `orchestrator/tests/test_context_merge.py`
- `orchestrator/tests/test_merge_status.py`
- `orchestrator/tests/test_runtime_adapters.py`
- `orchestrator/tests/test_git_service.py`

## Things to avoid

Do not:

- revive or edit old `apps/orchestrator-v2/` paths
- treat pi sessions/transcripts as canonical context
- add UI-driven shortcuts that bypass graph invariants
- merge context without ancestry
- mutate node code/context snapshots in place
- spread raw git subprocess calls outside `GitService`
- add new feature surface before clarifying merge conflict semantics
- assume ruff/mypy failures are acceptable final state

## Handoff bottom line

The orchestrator is a real alpha backend foundation, not a finished product.

The next work should focus on making the core graph semantics complete and trustworthy: conflicted merge semantics, conflict resolution, context projection/merge maturity, durable cancellation, artifact APIs, event replay semantics, and state integrity.
