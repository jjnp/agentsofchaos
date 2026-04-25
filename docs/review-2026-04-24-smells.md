# Orchestrator Review — 2026-04-24

Observations collected during the backend ↔ frontend integration smoke
test. Fix status updated 2026-04-25.

## Status

| #  | Smell                                            | Status   |
|----|--------------------------------------------------|----------|
| 1  | Duplicate SSE event delivery                     | **fixed**    |
| 2  | Mixed payload casing (snake/camel)               | open     |
| 3  | `noop` backend reports `runtime: "custom"`       | open     |
| 4  | `runtime_backend` literal disagrees with enum    | open     |
| 5  | Missing `GET /projects/{id}/nodes/{node_id}`     | **fixed**    |
| 6  | Missing diff endpoints                            | **partial** (code diff shipped; context diff still out) |
| 7  | Default sqlite path is CWD-relative              | open     |
| 8  | `/merges` same-node returns 409 with bad code    | open     |
| 9  | Merge test coverage gap                          | **partial** (unit tests of `_merge_status` shipped; e2e for `*_conflicted` still missing) |

---

## TL;DR

- **One real bug**: SSE emits `run_started` twice per run. Idempotent consumers are safe; non-idempotent ones will double-count. _(fixed)_
- **One consistent foot-gun**: event wrappers are snake_case, their `payload` bodies are camelCase. Every consumer hits this once.
- **Two naming confusions**: the `noop` settings backend reports itself as `runtime: "custom"`; `Literal["noop", "pi"]` disagrees with the `RuntimeKind` enum.
- **Two missing endpoints**: `GET /projects/{id}/nodes/{node_id}` _(fixed)_ and diff endpoints _(code diff shipped; context diff still out)_.
- **Test coverage gap**: `context_conflicted` and `both_conflicted` statuses exist but aren't exercised end-to-end. _(unit-level coverage of the classifier shipped)_

---

## 1. Duplicate SSE event delivery — _fixed_

**Evidence.** During an SSE trace of a second prompt run, the same `run_started` event record (id `68341298-b412-4bb9-bc43-80297530c08f`) was delivered twice consecutively:

```
event: run_started
data: {"id":"68341298-b412-4bb9-bc43-80297530c08f",…}

event: run_started
data: {"id":"68341298-b412-4bb9-bc43-80297530c08f",…}
```

Same id, same payload, back-to-back.

**Hypothesis.** architecture.md §10 says "Pre-1.0 may still publish inline after commit, but durable publishing must go through an explicit outbox dispatcher boundary so the system can converge on background dispatch without changing event semantics." The likely cause is both an inline `event_bus.publish(...)` _and_ the `OutboxDispatchWorker` replaying the same record.

**Impact.** Idempotent consumers (the `GraphStore` does a full `refreshGraph()` on node events) are safe. Non-idempotent ones — anything appending to a terminal, counting tokens per event, or writing a transcript line per event — will double-count.

**Fix landed.** `OutboxRepository.mark_published` now atomically claims a row via `UPDATE … WHERE published_at IS NULL` and returns whether the claim succeeded. `OutboxDispatcher.dispatch_event` reorders to mark-then-publish: only the call that wins the claim publishes to the bus. Verified live by tracing 3 back-to-back prompts and confirming exactly 3 events per topic, no duplicates.

---

## 2. Mixed payload casing — _open_

**Evidence.** From the SSE trace:

```json
{
  "id": "...",
  "project_id": "...",
  "topic": "run_created",
  "payload": {
    "projectId": "...",
    "runId": "...",
    "sourceNodeId": "...",
    "plannedChildNodeId": "..."
  },
  "created_at": "..."
}
```

Wrapper: snake_case (Pydantic's default emission of field names). Payload: camelCase (hand-built by whichever service records the event).

**Impact.** Cost us one bug in `frontend/src/lib/agent-graph/state.svelte.ts` (`payload['run_id']` had to become `payload['runId']`). Every new consumer will hit the same trap. Also hurts grep-ability: you can't find all uses of a given field name without knowing which side of the boundary you're on.

**Fix (recommended).** Rewrite payload dicts to use snake_case. Keeps the system internally consistent with Python's conventions. Alternative (camelCase everywhere via FastAPI `alias_generator`) is a bigger change and doesn't match the Pydantic-native style the codebase already uses.

**Where to look.** Every `ApplicationEventRecorder` call site that builds payload dicts. Likely `application/runs.py`, `application/project_nodes.py`, `application/merges.py`.

---

## 3. `noop` backend reports `runtime: "custom"` — _open_

**Evidence.**

- `infrastructure/settings.py`: `runtime_backend: Literal["noop", "pi"] = "noop"`.
- `RuntimeKind` enum (`domain/enums.py`): `LOCAL_SUBPROCESS | PI | CLAUDE_CODE | CODEX | CUSTOM`.
- Smoke test run response: `"runtime": "custom"` when the daemon was configured with `runtime_backend=noop`.

**Impact.** A human inspecting a run cannot distinguish "default no-op adapter" from "genuine user-plugged custom runtime." `custom` is meant to be the escape-hatch slot per runtime-adapters.md §9.2; consuming it for the default adapter is a category error.

**Fix.** Add `RuntimeKind.NOOP = "noop"` and have `NoOpRuntimeAdapter` report it. Alternatively, drop `custom` entirely if no one is plugging a custom adapter yet — YAGNI.

---

## 4. `runtime_backend` literal disagrees with `RuntimeKind` — _open_

**Evidence.** `Literal["noop", "pi"]` in settings vs `RuntimeKind` with 5 values. runtime-adapters.md §9.2 and ADR-0005 both explicitly plan for `ClaudeCodeRuntimeAdapter` and `CodexRuntimeAdapter`.

**Impact.** Adding a new runtime requires two synchronous changes (enum + settings literal). Easy to forget one.

**Fix.** Derive the settings type from the enum: `runtime_backend: RuntimeKind = RuntimeKind.NOOP` (after fix #3 above). Validation happens for free; new adapters need one enum entry, not two.

---

## 5. Missing `GET /projects/{id}/nodes/{node_id}` — _fixed_

**Evidence.** `api/routes/projects.py` previously had endpoints to create a root node and to prompt from a node, but no way to fetch a single node by id. implementation-plan.md §3 listed `GET /nodes/{node_id}` as a recommended initial endpoint.

**Impact (was).** Every consumer that wants one node had to fetch the whole graph. Scales poorly once graphs get real, and complicates incremental UI updates after an event lands.

**Fix landed.** `QueryService.get_node(project_id, node_id)` enforces project ownership and raises `NodeNotFoundError` (mapped to `404 NODE_NOT_FOUND` by the existing handler). Route `GET /projects/{project_id}/nodes/{node_id}` returns `NodeResponse`. Frontend now uses `client.getNode()` to refresh single nodes after events.

---

## 6. Missing diff endpoints — _partial_

**Evidence.** architecture.md §14 step 5 is "inspect code and context diffs between nodes." `GitService` already exposed diff primitives internally; no HTTP surface.

**Fix landed (code diff).** `GET /projects/{project_id}/nodes/{node_id}/diff` returns parsed `FileDiff[]` with hunks, totals, and base/head commit SHA. Powered by a new `application/diffs.py` (`DiffApplicationService` + a unified-diff parser handling rename/delete/binary headers). The frontend's `Changes` tab consumes it directly.

**Still open (context diff).** `GET /diffs/context` not implemented; the typed three-way context comparison from context-model.md §8 has no HTTP surface yet. The `Context` tab in the inspector reads the full context snapshot, not a diff.

---

## 7. Default sqlite path is CWD-relative — _open_

**Evidence.** `database_url: str = "sqlite+aiosqlite:///./.aoc-orchestrator.sqlite3"` in settings.py.

**Impact.** Starting the daemon from two different directories silently produces two different databases. architecture.md §5.3 says daemon state should live under `.aoc/` inside the managed repo root — and indeed worktrees and transcripts land there correctly. Only the top-level DB dangles in cwd.

**Fix options.** (a) XDG state dir default (`$XDG_STATE_HOME/agentsofchaos/db.sqlite3`); (b) fail loudly on startup if `AOC_DATABASE_URL` is unset. (a) is friendlier, (b) is more explicit.

---

## 8. `/merges` same-node error returns 409 with a misleading code — _open_

**Evidence.**

```
POST /projects/{id}/merges   {source_node_id: X, target_node_id: X}
→ HTTP 409  {"error":{"code":"MERGE_ANCESTOR_ERROR","message":"Cannot merge a node with itself"}}
```

**Impact.** 409 Conflict is for "resource state conflicts with the request." Same-node is a request-validation error — 422 Unprocessable Entity fits. `MERGE_ANCESTOR_ERROR` is also a misleading code name for a same-node check.

**Fix.** 422 for validation, dedicated error code (`MERGE_INVALID_NODES` or similar). Keep `MERGE_ANCESTOR_ERROR` for its actual use (no common ancestor between two distinct nodes).

---

## 9. Merge test coverage gap — _partial_

**Evidence (was).**

- `tests/test_merge_flow.py`: clean merge, code-conflicted merge.
- `tests/test_context_merge.py`: divergent-edit (unit-level), one-sided-edit (unit-level).

Missing: full-pipeline tests that produce `context_conflicted` or `both_conflicted` node statuses.

**Fix landed (classifier unit tests).** New `tests/test_merge_status.py` exercises the `_merge_status()` classifier across all four outcomes (`READY`, `CODE_CONFLICTED`, `CONTEXT_CONFLICTED`, `BOTH_CONFLICTED`) plus multi-conflict variants. The classifier is now pinned independently of context-projection maturity.

**Still open (e2e).** No `MergeApplicationService.merge_nodes()` test produces a `context_conflicted` or `both_conflicted` node end-to-end. The current context projection always emits items with fresh UUIDs, so siblings can't naturally produce divergent-edit context items. Closing this requires either a projection that can emit deterministic ids or a test seam to plant context items into source/target snapshots before the merge call.

Golden-path conflict tests are called mandatory by implementation-plan.md §6 (Phase 5).

---

## Non-smells considered

- **`frontend/` uncommitted changes**: intentional, hackathon artifact.
- **`allow_existing_root_node: bool = False`**: a config knob, not a smell.
- **`RuntimeCapability` enum exists but isn't used in `RuntimeAdapter` protocol yet**: likely staging ground for future capability negotiation (runtime-adapters.md §5). Not a smell, a WIP.

---

## Priority suggestion (remaining)

1. Payload casing (§2) — every new consumer will hit it once.
2. Noop/custom naming (§3) + runtime_backend literal (§4) — combine into one small refactor.
3. Context diff endpoint (§6 partial) — finish the Changes/Context inspector loop.
4. E2E merge coverage (§9 partial) — fill the conflict-status test matrix.
5. DB path default (§7), 409 vs 422 (§8) — nice-to-haves.

None of these block frontend development. They just shape which integrations stay simple and which grow warts.
