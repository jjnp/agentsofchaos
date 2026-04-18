# Orchestrator API

Single-user, no-auth API for the global orchestrator.

## Model

There is one global orchestrator process with:
- one shared instance graph
- one shared event stream
- no user/session auth layer

All instance slots are global within the running process.

## Transports

- REST for commands and reads
- SSE for real-time events
- WebSocket remains supported for existing clients

Base URL examples:
- HTTP: `http://127.0.0.1:3000`
- SSE: `http://127.0.0.1:3000/api/events/stream`
- WebSocket: `ws://127.0.0.1:3000`

---

## REST Endpoints

### `GET /api/state`
Returns the full current orchestrator state.

#### Response
```json
{
  "sessionId": "b49645d87d60",
  "model": "openai/gpt-5.4-mini",
  "mergeModel": "gpt-5.4-mini",
  "instanceCount": 0,
  "instances": []
}
```

### `GET /api/instances`
Returns all live instances.

#### Response
```json
{
  "instances": []
}
```

### `POST /api/instances`
Creates a new worker instance.

#### Response
```json
{
  "slot": 0,
  "label": "pi-1",
  "agentUuid": "piagent_..."
}
```

### `GET /api/instances/:slot`
Returns one normalized instance record.

#### Response
```json
{
  "slot": 0,
  "label": "pi-1",
  "agentUuid": "piagent_...",
  "containerName": "aoc-piagent_...",
  "sessionId": "uuid",
  "sourceImage": "agentsofchaos/pi-worker:latest",
  "status": "running",
  "lastGitStatus": "## main...origin/main",
  "lastForkPoint": null
}
```

### `POST /api/instances/:slot/prompt`
Queues a prompt for an instance.

#### Body
```json
{
  "message": "Implement feature X"
}
```

#### Response
```json
{
  "accepted": true,
  "slot": 0,
  "queuedAt": 1776514597202
}
```

Completion should be detected from the SSE or websocket event stream via `pi_event` / `agent_end`.

### `POST /api/instances/:slot/explain-file`
Explains one changed file from the instance's fork point.

#### Body
```json
{
  "filePath": "frontend/src/routes/+page.svelte",
  "mode": "direct"
}
```

Modes:
- `direct` — summarize using fork-point summary + file diff
- `ephemeral` — spawn a temporary analysis worker from the instance snapshot and ask pi directly

#### Response
```json
{
  "slot": 1,
  "filePath": "frontend/src/routes/+page.svelte",
  "mode": "direct",
  "summary": "This branch updates the route component to wire the graph canvas into the page. It likely changed to surface the branching workflow in the UI, and the main risk is coupling the page too tightly to demo-specific state assumptions.",
  "forkPointCapturedAt": 1776510000000
}
```

### `POST /api/instances/:slot/fork`
Forks an instance by capturing fork-point metadata and snapshotting its container.

#### Response
```json
{
  "sourceSlot": 0,
  "targetSlot": 1,
  "targetLabel": "pi-2",
  "image": "agentsofchaos/pi-snapshot:...",
  "forkPoint": {
    "reason": "fork",
    "capturedAt": 1776510000000,
    "git": {
      "shortHead": "abc123def456",
      "shortStat": "2 files changed, 10 insertions(+), 3 deletions(-)",
      "changedFiles": ["src/foo.ts"]
    },
    "contextUsage": {
      "totalTokens": 12345,
      "latestResponseTokens": 812,
      "assistantMessages": 9
    },
    "summary": {
      "format": "pi-branch-summary-v1",
      "preview": "Capture a stable fork point for pi-1 during fork.",
      "nodeTitle": "Frontend Orchestrator Sync",
      "readFiles": ["src/foo.ts"],
      "modifiedFiles": ["src/foo.ts"]
    }
  }
}
```

### `POST /api/instances/:slot/stop`
Stops and removes a worker.

#### Response
```json
{
  "ok": true,
  "slot": 0,
  "label": "pi-1",
  "agentUuid": "piagent_..."
}
```

### `POST /api/merge-prep`
Prepares a git bundle merge without executing the final merge.

#### Body
```json
{
  "sourceSlot": 1,
  "targetSlot": 0
}
```

#### Response
```json
{
  "sourceSlot": 1,
  "targetSlot": 0,
  "remoteName": "merge_slot_2",
  "bytes": 98522,
  "nextStep": "git -C /workspace merge merge_slot_2/main || git -C /workspace log --oneline --all --graph"
}
```

### `POST /api/merge`
Performs a non-destructive integration merge.

#### Body
```json
{
  "sourceSlot": 1,
  "targetSlot": 0
}
```

#### Response
```json
{
  "sourceSlot": 1,
  "targetSlot": 0,
  "integrationSlot": 3,
  "remoteName": "merge_slot_2",
  "mergeExitCode": 0,
  "mergeContextPath": "/state/meta/merge-context.md"
}
```

Semantics:
- target is not modified directly
- a new integration instance is created from the target
- source bundle is imported into the integration instance
- a real `git merge` is executed there

---

## Artifact Endpoints

### `GET /api/instances/:slot/artifacts/fork-point`
Returns parsed JSON from `/state/meta/fork-point.json`.

The fork-point artifact now also includes a pi-style branch summary in:
- `summary.format`
- `summary.markdown`
- `summary.preview`
- `summary.nodeTitle`
- `summary.readFiles`
- `summary.modifiedFiles`

### `GET /api/instances/:slot/artifacts/merge-details`
Returns parsed JSON from `/state/meta/merge-details.json`.

### `GET /api/instances/:slot/artifacts/merge-context`
Returns markdown from `/state/meta/merge-context.md`.

Content type:
- `text/markdown; charset=utf-8`

If an artifact is missing, the server returns:
```json
{
  "error": {
    "code": "ARTIFACT_NOT_FOUND",
    "message": "..."
  }
}
```

---

## SSE Event Stream

### `GET /api/events/stream`
Subscribes to the global orchestrator event stream.

Content type:
- `text/event-stream`

Each event is emitted as:
```text
event: message
data: {"type":"instance_created","slot":0,"label":"pi-1"}
```

The server also replays recent buffered events from memory on connect.

### Important event types

Bootstrap:
- `grid_boot`
- `grid_ready`

Instance lifecycle:
- `worker_container_started`
- `session_ready`
- `instance_created`
- `instance_stopped`

Streaming / agent execution:
- `session_output`
- `assistant_delta`
- `pi_event`

Git / merge:
- `git_status`
- `checkpoint_created`
- `bundle_exported`
- `bundle_imported`
- `git_merge_succeeded`
- `git_merge_conflicted`
- `merge_context_written`

Fork / integration metadata:
- `fork_point_recorded`
- `fork_complete`
- `merge_integration_created`
- `merge_complete`

### Completion rule for prompts
A prompt is considered complete when the stream emits:
```json
{
  "type": "pi_event",
  "event": {
    "type": "agent_end"
  }
}
```
for the target slot.

---

## Error Model

Errors are returned as JSON:
```json
{
  "error": {
    "code": "INVALID_SLOT",
    "message": "Invalid slot: 9"
  }
}
```

Common codes:
- `BAD_REQUEST`
- `INVALID_SLOT`
- `ARTIFACT_NOT_FOUND`
- `INTERNAL_ERROR`
- `NOT_FOUND`

---

## Agent-Compatible Usage Pattern

Recommended control flow for another agent or frontend:

1. `GET /api/state`
2. connect to `GET /api/events/stream`
3. `POST /api/instances`
4. `POST /api/instances/:slot/prompt`
5. wait for `pi_event.event.type === "agent_end"`
6. use `POST /api/instances/:slot/fork` or `POST /api/merge` as needed
7. inspect artifacts through `/api/instances/:slot/artifacts/*`

For graph UIs:
- model `fork_complete` as parent -> child edge
- model `merge_integration_created` as target -> integration edge
- model `merge_complete` as source -> integration merge edge
