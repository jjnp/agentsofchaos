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

- project open
- root node creation
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
PYTHONPATH=. uv run pytest -q
uv run python -m compileall src tests
```

At the time of this note:

```text
PYTHONPATH=. uv run pytest -q
```

passes:

```text
23 passed
```

Plain `uv run pytest` fails because tests import `tests.helpers` and `tests/` is not currently a package. Either add `tests/__init__.py`, adjust imports, or keep `PYTHONPATH=.` until this is fixed.

Ruff and mypy are **not clean** yet.

Known ruff categories:

- import ordering
- FastAPI `Depends(...)` flagged by B008
- `datetime.UTC` modernization
- `repositories.py` import placement
- `event_bus.py` return inside `finally`
- async pathlib warnings

Useful mypy invocation that avoids package-resolution noise:

```bash
MYPYPATH=src:. uv run mypy --explicit-package-bases src tests
```

This currently reduces to a small set of substantive typing issues, including:

- `GitService` generic error-type defaults
- `ArtifactRecorder._persist_artifacts` run id optionality mismatch
- `RunSupervisor` accepting `Awaitable` where `asyncio.create_task` wants a coroutine
- pi process protocol mismatch with `asyncio.subprocess.Process`
- report JSON indexing in tests without narrowing

Do not interpret mypy's larger default output as purely application problems; some is invocation/package-path configuration.

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

Merges can produce conflicted merge nodes, but there is no backend workflow to resolve them.

Needed:

- typed conflict models
- code conflict resolution API
- context conflict resolution API
- validation/finalization
- provenance for resolution decisions
- clear decision: mutate conflicted node status or create successor resolution node

### 2. Conflicted code snapshot semantics

Current code merge behavior can commit conflict-marker files into a `code_conflicted` merge node.

This may be acceptable as a durable conflicted workspace snapshot, but it must be an explicit architecture decision.

Decide:

- Are conflicted code snapshots allowed to contain conflict markers?
- Are they integration snapshots or conflicted workspace snapshots?
- What creates the eventual clean integrated snapshot?

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

1. Decide and document conflicted merge semantics.
2. Implement backend merge conflict resolution or a clear resolution-node model.
3. Add typed conflict/report domain models.
4. Build `PiContextProjector` and projection report artifacts.
5. Add context diff API.
6. Make cancellation durable and inspectable.
7. Add artifact listing/metadata/content APIs.
8. Tighten outbox replay semantics.
9. Add state integrity checks.
10. Then clean ruff/mypy baselines.

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
