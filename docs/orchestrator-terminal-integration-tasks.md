# Orchestrator + Terminal Integration Task Set

This is the step-by-step task set for integrating the current graph frontend with the orchestrator backend, with special attention to live and replayed terminal output.

## Quick assessment: terminal integration

### What already exists

- `frontend/src/lib/components/TerminalStream.svelte`
  - strong xterm-based terminal rendering
  - currently assumes a **direct websocket transport**
  - also assumes interactive raw terminal input / resize messages
- `frontend/src/lib/components/agent-graph/AgentNodeViewSidebar.svelte`
  - already has the correct **selected-node inspector role**
  - currently uses placeholder log text
- `apps/orchestrator` / `apps/pi-worker`
  - already emit the right execution stream semantics:
    - `session_output`
    - `assistant_delta`
    - `pi_event`
    - `session_ready`
    - `session_exit`

### Key integration conclusion

The current terminal visualization is usable, but the transport model is wrong for the orchestrator-backed graph.

The orchestrator frontend flow should **not** depend on a dedicated websocket-per-node terminal component. Instead, it should:

- bootstrap state via REST
- subscribe to the orchestrator SSE stream
- buffer output per node in frontend state
- render the selected node’s buffered output in the terminal UI
- append live output to the same buffer while a node is running

### Recommended terminal direction

Refactor toward a split like this:

- `TerminalSurface` or equivalent xterm-based renderer
- one transport adapter for websocket/demo usage if we still want it
- one orchestrator-backed feed mode for append/replay from frontend state

That gives us:

- **live streamed output** for running nodes
- **historical replay** for completed nodes
- no duplicated terminal implementations

---

## Task set

### 1. Add typed orchestrator transport layer

Create a typed REST + SSE client for the orchestrator.

**Why**
We need a strict seam between frontend UI and backend transport.

**Includes**

- typed API models for REST payloads
- typed event models for SSE payloads
- reconnect/bootstrap behavior
- no transport logic inside UI components

---

### 2. Build graph reducer from orchestrator state/events

Translate orchestrator state and live events into the existing graph domain.

**Why**
The canvas already expresses the right product model. We should preserve it and feed it from backend data.

**Includes**

- backend metadata beside node identity
- instance normalization
- fork lineage mapping
- merge integration mapping
- running/completed derivation from event flow
- frontend-owned placements remain separate

---

### 3. Refactor terminal visualization for orchestrator event feeds

Make the terminal visualization transport-agnostic.

**Why**
`TerminalStream.svelte` is currently websocket-centric, while orchestrator integration is state/event-centric.

**Includes**

- decide between extracting a `TerminalSurface` or adding a feed mode
- preserve xterm quality
- support append/replay from frontend state
- keep raw prompt submission separate from terminal keystroke transport

---

### 4. Replace node-view placeholders with real output history

Make the left sidebar show actual output for the selected node.

**Why**
Selecting a running node should show live output; selecting a completed node should show stored output in the same view.

**Includes**

- selected-node output binding
- live append while running
- historical replay for completed nodes
- clean switching between selected nodes

---

### 5. Replace prompt flow with orchestrator-backed execution

Wire the prompt composer to the selected node’s backend slot.

**Why**
Prompting is the smallest meaningful backend-backed interaction and unlocks live streaming.

**Includes**

- `POST /api/instances/:slot/prompt`
- running state starts on dispatch
- completion only on `pi_event.event.type === agent_end`
- selected-node terminal updates from event stream

---

### 6. Replace fork flow with orchestrator-backed lineage

Use real fork creation instead of local mock child synthesis.

**Why**
Fork lineage is core to the graph model and already exists in the backend.

**Includes**

- `POST /api/instances/:slot/fork`
- child node creation from orchestrator responses/events
- optional fork-point artifact hydration into node details

---

### 7. Replace merge flow with orchestrator integration-instance semantics

Keep the current merge UI but back it with real merge behavior.

**Why**
The orchestrator’s merge model matches our current graph visualization well: a new integration child plus a merged edge from the source.

**Includes**

- `POST /api/merge`
- integration node creation from merge events
- dashed merged edge from source to integration child
- future merge artifact hydration

---

### 8. Add artifact hydration for durable completed-node inspection

Use orchestrator artifacts to enrich nodes beyond live stream text.

**Why**
Completed nodes should remain inspectable after live output ends.

**Includes**

- fork-point artifact
- merge-details artifact
- merge-context markdown
- per-node artifact loading/error state

---

### 9. Verify and document the local orchestrator startup workflow

Make sure the backend can actually run during this integration effort.

**Why**
This work depends on the real backend loop being available during development.

**Includes**

- confirm Docker is running
- ensure `apps/orchestrator/.env` exists
- ensure `OPENAI_API_KEY` is set
- start with:
  ```bash
  cd apps/orchestrator
  ./dev-up.sh
  ```
- verify with:
  ```bash
  curl http://localhost:3000/api/state
  curl -N http://localhost:3000/api/events/stream
  ```
- optionally run:
  ```bash
  cd apps/orchestrator
  npm run e2e
  npm run battle:e2e
  ```

---

## Recommended implementation order

1. typed orchestrator client
2. graph reducer/store
3. terminal refactor to feed/replay mode
4. selected-node live/historical output in sidebar
5. prompt integration
6. fork integration
7. merge integration
8. artifact hydration
9. polish / richer status model

## Commit strategy

This is large enough to land in small slices:

- commit 1: typed orchestrator transport layer
- commit 2: reducer + backend-aware graph model
- commit 3: terminal refactor
- commit 4: selected-node live output wiring
- commit 5: prompt backend integration
- commit 6: fork backend integration
- commit 7: merge backend integration
- commit 8: artifact hydration and inspector polish

## Verified local backend workflow

The orchestrator stack can be started locally with:

```bash
cd apps/orchestrator
docker compose up -d --build
```

Verified checks:

```bash
curl http://127.0.0.1:3000/api/state
curl -N http://127.0.0.1:3000/api/events/stream
```

This is enough to support the next frontend integration slices while developing against the real backend.
