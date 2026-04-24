# Python Orchestrator V2 Design

## Goal

Replace the current Node.js orchestrator with a robust Python control plane that preserves the core product semantics:

- one worker container per agent instance
- checkpoint-first branching
- git-native merge transport
- non-destructive integration merges
- durable operation history
- restart-safe orchestration
- SSE/WebSocket event streaming for the UI

This document is intentionally architecture-first. The new orchestrator should be easier to reason about, test, recover, and evolve than the current single-file prototype.

## Design Principles

1. **Durable state first**
   - The orchestrator must have a single durable metadata source of truth.
   - Docker state and worker filesystem state are external systems that are reconciled against persisted orchestrator state.

2. **Operations are jobs**
   - Long-running actions like prompt, checkpoint, fork, merge, and stop are modeled as durable operations.
   - HTTP requests create or inspect operations; background workers execute them.

3. **Checkpoint-first semantics**
   - Forks should operate from an explicit checkpoint or create one first.
   - Mid-run mutable state should not be treated as a stable fork boundary.

4. **Single-writer per instance**
   - Only one mutating operation can own an instance at a time.
   - Merge acquires locks for source, target, and the new integration instance.

5. **Infrastructure behind interfaces**
   - Docker, worker RPC, git transport, artifact storage, and LLM summaries sit behind adapter interfaces.
   - Application logic should be testable without Docker.

6. **Crash recovery is a core feature**
   - On startup the orchestrator reconciles incomplete operations, running containers, and persisted metadata.

## Runtime Stack

- **Python 3.12+**
- **FastAPI** for HTTP API
- **Uvicorn** for local serving
- **SQLAlchemy 2.x** for persistence
- **SQLite** as the default durable store
- **Pydantic 2** / `pydantic-settings` for settings and DTOs
- **Docker SDK for Python** for container lifecycle
- **AnyIO / asyncio** for background job execution and SSE fanout
- **pytest** for tests

SQLite is the default because the current system is single-node and local-first. It gives strong enough durability with far less operational overhead than PostgreSQL. The persistence layer should still be written so a PostgreSQL backend is possible later.

## Proposed Package Layout

```text
apps/orchestrator-py/
  pyproject.toml
  README.md
  src/agentsofchaos_orchestrator/
    api/
      app.py
      dependencies.py
      routes/
        health.py
        state.py
        instances.py
        operations.py
        events.py
    application/
      services.py
      operation_runner.py
      locking.py
      reconciliation.py
    domain/
      enums.py
      models.py
      events.py
      commands.py
      errors.py
    infrastructure/
      db.py
      orm.py
      repositories.py
      event_bus.py
      runtime.py
      settings.py
    main.py
  tests/
```

## Domain Model

### Core entities

- **Instance**
  - logical agent branch node
  - references current worker container, image, git head, and latest session path

- **Checkpoint**
  - stable fork boundary
  - captures git commit, snapshot image ref, and latest session path

- **Operation**
  - durable job record
  - one of: `create_root`, `prompt`, `checkpoint`, `fork`, `merge`, `stop`, `explain_file`

- **Artifact**
  - persisted output such as fork point JSON, merge context markdown, merge details JSON

- **EventRecord**
  - append-only orchestrator event stream record for SSE / debugging / replay

### Instance lifecycle

States:

- `creating`
- `idle`
- `busy`
- `stopping`
- `stopped`
- `failed`
- `conflicted`

### Operation lifecycle

States:

- `pending`
- `running`
- `succeeded`
- `failed`
- `cancelled`

An operation record includes:

- type
- status
- source / target / integration instance ids where relevant
- attempt count
- structured metadata JSON
- structured error fields
- timestamps

## Persistence Schema

### instances

- `id`
- `label`
- `status`
- `parent_instance_id`
- `root_instance_id`
- `worker_container_name`
- `worker_container_id`
- `worker_image_ref`
- `workspace_git_head`
- `latest_session_path`
- `last_error`
- `created_at`
- `updated_at`
- `stopped_at`

### checkpoints

- `id`
- `instance_id`
- `reason`
- `git_commit`
- `snapshot_image_ref`
- `session_path`
- `metadata_json`
- `created_at`

### operations

- `id`
- `type`
- `status`
- `instance_id`
- `source_instance_id`
- `target_instance_id`
- `integration_instance_id`
- `metadata_json`
- `error_code`
- `error_message`
- `created_at`
- `started_at`
- `finished_at`

### artifacts

- `id`
- `instance_id`
- `kind`
- `content_type`
- `storage_path`
- `metadata_json`
- `created_at`

### event_records

- `id`
- `topic`
- `instance_id`
- `operation_id`
- `payload_json`
- `created_at`

## Adapter Interfaces

### WorkerRuntime

Responsibilities:

- create worker container from image
- connect to worker RPC websocket
- send prompt
- stop worker
- inspect worker health
- copy files in/out
- exec commands in container
- commit snapshot image

### GitService

Responsibilities:

- ensure workspace repo
- get git status / head / diff summary
- create checkpoint commit if dirty
- export bundle
- import bundle
- perform merge

### ArtifactStore

Responsibilities:

- persist fork point JSON
- persist merge details JSON
- persist merge context markdown
- fetch artifacts by instance + kind

### SummaryService

Responsibilities:

- summarize fork points
- summarize merge context
- explain changed files

The summary service must be optional. The orchestrator should still function if model access is unavailable.

## Operation Flows

### Create root instance

1. create `create_root` operation row
2. acquire global root-creation guard
3. create instance row with `creating`
4. create worker container from base image
5. initialize worker connection metadata
6. inspect git status
7. mark instance `idle`
8. emit instance-created event
9. mark operation succeeded

### Prompt instance

1. create `prompt` operation row
2. acquire instance lock
3. mark instance `busy`
4. send prompt to worker RPC
5. stream events as the worker responds
6. wait for `agent_end`
7. inspect latest session + git state
8. optionally create idle checkpoint
9. mark instance `idle`
10. mark operation succeeded

### Checkpoint instance

1. create `checkpoint` operation row
2. acquire instance lock
3. checkpoint commit if git dirty
4. read git head and latest session path
5. commit snapshot image
6. persist checkpoint row
7. emit checkpoint-created event
8. mark operation succeeded

### Fork instance

1. create `fork` operation row
2. acquire source instance lock
3. resolve checkpoint to fork from
   - explicit checkpoint id if provided
   - else latest checkpoint
   - else create checkpoint first
4. create child instance row with `creating`
5. create worker from checkpoint snapshot image
6. persist parent/root relationships
7. inspect git state
8. mark child `idle`
9. emit fork-complete event
10. mark operation succeeded

### Merge instances

1. create `merge` operation row
2. acquire locks for source and target
3. resolve target integration base checkpoint
4. create integration instance from target checkpoint snapshot
5. export git bundle from source checkpoint
6. import bundle into integration instance
7. execute real git merge
8. persist merge artifacts
9. if merge conflict, mark integration instance `conflicted`
10. else mark integration instance `idle`
11. emit merge-complete event
12. mark operation succeeded

## Locking Rules

- one mutating operation per instance
- prompt, checkpoint, fork-from, merge-source, merge-target, and stop are mutating
- read endpoints do not acquire locks
- merge acquires locks in stable sorted instance-id order to avoid deadlocks
- stop is exclusive and should fail fast if another operation is running unless forced

## Recovery Rules

On startup:

1. load all operations with `pending` or `running`
2. inspect Docker for referenced worker containers
3. inspect instances in `creating`, `busy`, or `stopping`
4. mark stale operations as failed or resumable according to their last durable step
5. repair instance statuses:
   - missing container for `busy` instance -> `failed`
   - present healthy container for `busy` instance with no active operation -> `idle` or `failed-recovery-needed`
6. emit reconciliation events

The recovery process should be idempotent.

## API Compatibility Strategy

Keep the current high-level routes if practical:

- `GET /api/state`
- `GET /api/events/stream`
- `POST /api/instances`
- `GET /api/instances`
- `GET /api/instances/{slot_or_id}`
- `POST /api/instances/{slot_or_id}/prompt`
- `POST /api/instances/{slot_or_id}/fork`
- `POST /api/instances/{slot_or_id}/stop`
- `POST /api/merge`

Internally the new orchestrator should prefer stable UUID instance ids. If the frontend still expects integer slots, add a presentation-layer compatibility mapping.

## Why Python

Python is a good fit here because:

- Docker and Git automation are strong and mature
- background job orchestration is straightforward
- the code can be more declarative and modular than the current mega-file JS server
- type checking with Pydantic + mypy/pyright is good enough for a robust control plane
- operational debugging tends to be simpler for systems glue code

## Implementation Phases

### Phase 1

- app skeleton
- settings
- SQLite persistence
- event bus
- health + state endpoints
- durable operation model

### Phase 2

- create root
- stop instance
- prompt operation record + streaming plumbing

### Phase 3

- checkpoints
- fork
- artifact persistence

### Phase 4

- merge integration flow
- conflict handling
- reconciliation on startup

### Phase 5

- frontend compatibility
- explain-file summaries
- richer observability

## Non-Goals for V2

- distributed orchestration
- Kubernetes-native scheduling
- multi-user auth
- horizontally scaled event bus
- replacing the worker runtime

The point of this rewrite is to make the current single-node product semantics durable and trustworthy, not to prematurely turn it into a cloud platform.
