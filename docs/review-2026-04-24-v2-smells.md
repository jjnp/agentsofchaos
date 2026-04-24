# Orchestrator v2 Review — 2026-04-24

Observations collected during the v2 backend ↔ frontend-v2 integration smoke test.

## TL;DR

- **One real bug**: SSE emits `run_started` twice per run. Idempotent consumers are safe; non-idempotent ones will double-count.
- **One consistent foot-gun**: event wrappers are snake_case, their `payload` bodies are camelCase. Every consumer hits this once.
- **Two naming confusions**: the `noop` settings backend reports itself as `runtime: "custom"`; `Literal["noop", "pi"]` disagrees with the `RuntimeKind` enum.
- **Two missing endpoints**: `GET /projects/{id}/nodes/{node_id}` (recommended in the plan, never implemented); `/diffs/code` + `/diffs/context` (needed for architecture.md §14 step 5).
- **Test coverage gap**: `context_conflicted` and `both_conflicted` statuses exist but aren't exercised end-to-end.

---

## 1. Duplicate SSE event delivery _(real bug)_

**Evidence.** During an SSE trace of a second prompt run, the same `run_started` event record (id `68341298-b412-4bb9-bc43-80297530c08f`) was delivered twice consecutively:

```
event: run_started
data: {"id":"68341298-b412-4bb9-bc43-80297530c08f",…}

event: run_started
data: {"id":"68341298-b412-4bb9-bc43-80297530c08f",…}
```

Same id, same payload, back-to-back.

**Hypothesis.** architecture.md §10 says "Pre-1.0 may still publish inline after commit, but durable publishing must go through an explicit outbox dispatcher boundary so the system can converge on background dispatch without changing event semantics." The likely cause is both an inline `event_bus.publish(...)` _and_ the `OutboxDispatchWorker` replaying the same record.

**Impact.** Idempotent consumers (my `GraphStore` does a full `refreshGraph()` on node events) are safe. Non-idempotent ones — anything appending to a terminal, counting tokens per event, or writing a transcript line per event — will double-count.

**Fix.** Pick one path (inline OR outbox) and make the other a no-op until the outbox fully replaces inline. Add a regression test: "publish N events → subscriber sees N, not 2N".

---

## 2. Mixed payload casing

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

**Impact.** Cost us one bug in `frontend-v2/src/lib/agent-graph/state.svelte.ts` (`payload['run_id']` had to become `payload['runId']`). Every new consumer will hit the same trap. Also hurts grep-ability: you can't find all uses of a given field name without knowing which side of the boundary you're on.

**Fix (recommended).** Rewrite payload dicts to use snake_case. Keeps the system internally consistent with Python's conventions. Alternative (camelCase everywhere via FastAPI `alias_generator`) is a bigger change and doesn't match the Pydantic-native style the codebase already uses.

**Where to look.** Every `ApplicationEventRecorder` call site that builds payload dicts. Likely `application/runs.py`, `application/project_nodes.py`, `application/merges.py`.

---

## 3. `noop` backend reports `runtime: "custom"`

**Evidence.**

- `infrastructure/settings.py`: `runtime_backend: Literal["noop", "pi"] = "noop"`.
- `RuntimeKind` enum (`domain/enums.py`): `LOCAL_SUBPROCESS | PI | CLAUDE_CODE | CODEX | CUSTOM`.
- Smoke test run response: `"runtime": "custom"` when the daemon was configured with `runtime_backend=noop`.

**Impact.** A human inspecting a run cannot distinguish "default no-op adapter" from "genuine user-plugged custom runtime." `custom` is meant to be the escape-hatch slot per runtime-adapters.md §9.2; consuming it for the default adapter is a category error.

**Fix.** Add `RuntimeKind.NOOP = "noop"` and have `NoOpRuntimeAdapter` report it. Alternatively, drop `custom` entirely if no one is plugging a custom adapter yet — YAGNI.

---

## 4. `runtime_backend` literal disagrees with `RuntimeKind`

**Evidence.** `Literal["noop", "pi"]` in settings vs `RuntimeKind` with 5 values. runtime-adapters.md §9.2 and ADR-0005 both explicitly plan for `ClaudeCodeRuntimeAdapter` and `CodexRuntimeAdapter`.

**Impact.** Adding a new runtime requires two synchronous changes (enum + settings literal). Easy to forget one.

**Fix.** Derive the settings type from the enum: `runtime_backend: RuntimeKind = RuntimeKind.NOOP` (after fix #3 above). Validation happens for free; new adapters need one enum entry, not two.

---

## 5. Missing `GET /projects/{id}/nodes/{node_id}`

**Evidence.** `api/routes/projects.py` has endpoints to create a root node and to prompt from a node, but no way to fetch a single node by id. implementation-plan.md §3 listed `GET /nodes/{node_id}` as a recommended initial endpoint.

**Impact.** Every consumer that wants one node has to fetch the whole graph. Scales poorly once graphs get real, and complicates incremental UI updates after an event lands.

**Fix.** Trivial — call an existing repository method.

---

## 6. Missing diff endpoints

**Evidence.** architecture.md §14 step 5 is "inspect code and context diffs between nodes." No `GET /diffs/code` or `GET /diffs/context` routes exist. `GitService` already exposes diff primitives internally.

**Impact.** Blocks the architectural success story from being end-to-end demonstrable. The UI can describe snapshot IDs but not their contents.

**Fix.** Add two endpoints. Code diff: thin wrapper over `git diff` between two snapshots' commit SHAs. Context diff: use the existing context comparison logic (per context-model.md §8).

---

## 7. Default sqlite path is CWD-relative

**Evidence.** `database_url: str = "sqlite+aiosqlite:///./.aoc-orchestrator-v2.sqlite3"` in settings.py.

**Impact.** Starting the daemon from two different directories silently produces two different databases. architecture.md §5.3 says daemon state should live under `.aoc/` inside the managed repo root — and indeed worktrees and transcripts land there correctly. Only the top-level DB dangles in cwd.

**Fix options.** (a) XDG state dir default (`$XDG_STATE_HOME/agentsofchaos/db.sqlite3`); (b) fail loudly on startup if `AOC_V2_DATABASE_URL` is unset. (a) is friendlier, (b) is more explicit.

---

## 8. `/merges` same-node error returns 409 with a misleading code

**Evidence.**

```
POST /projects/{id}/merges   {source_node_id: X, target_node_id: X}
→ HTTP 409  {"error":{"code":"MERGE_ANCESTOR_ERROR","message":"Cannot merge a node with itself"}}
```

**Impact.** 409 Conflict is for "resource state conflicts with the request." Same-node is a request-validation error — 422 Unprocessable Entity fits. `MERGE_ANCESTOR_ERROR` is also a misleading code name for a same-node check.

**Fix.** 422 for validation, dedicated error code (`MERGE_INVALID_NODES` or similar). Keep `MERGE_ANCESTOR_ERROR` for its actual use (no common ancestor between two distinct nodes).

---

## 9. Merge test coverage gap

**Evidence.**

- `tests/test_merge_flow.py`: clean merge, code-conflicted merge.
- `tests/test_context_merge.py`: divergent-edit (unit-level), one-sided-edit (unit-level).

Missing: full-pipeline tests that produce `context_conflicted` or `both_conflicted` node statuses.

**Impact.** Those two statuses are declared and classified in `_merge_status()`, but no test confirms the end-to-end wiring lands a node in either state correctly.

**Fix.** Two more cases in `test_merge_flow.py`:
1. Code identical, contexts diverge → node status `context_conflicted`.
2. Both code and contexts diverge → node status `both_conflicted`.

Golden-path conflict tests are called mandatory by implementation-plan.md §6 (Phase 5).

---

## Non-smells considered

- **`frontend/` uncommitted changes**: intentional, hackathon artifact.
- **`allow_existing_root_node: bool = False`**: a config knob, not a smell.
- **`RuntimeCapability` enum exists but isn't used in `RuntimeAdapter` protocol yet**: likely staging ground for future capability negotiation (runtime-adapters.md §5). Not a smell, a WIP.

---

## Priority suggestion

1. Duplicate SSE (§1) — real bug, affects every SSE consumer.
2. Payload casing (§2) — every new consumer will hit it once.
3. Missing `GET /nodes/{id}` (§5) — tiny to add, unblocks cleaner UI code paths.
4. Missing diff endpoints (§6) — unblocks arch §14 step 5.
5. Noop/custom naming (§3) + runtime_backend literal (§4) — combine into one small refactor.
6. Merge coverage (§9) — fill the conflict-status test matrix.
7. DB path default (§7), 409 vs 422 (§8) — nice-to-haves.

None of the above block frontend-v2 development. They just shape which integrations stay simple and which grow warts.
