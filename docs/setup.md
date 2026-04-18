# Setup Guide

This guide explains how to run the current single-user orchestrator demo locally.

## What you are starting

The current main system is:

- `apps/orchestrator/` — the control server
- `apps/pi-worker/` — the worker container image
- one Docker container per pi instance
- one global orchestrator state
- API/SSE/WebSocket control server on port `3000`
- REST + SSE + WebSocket control surfaces

## Prerequisites

You need:

- Docker installed and running
- Node.js available locally
- an OpenAI API key

Optional but useful:

- `npm`
- `curl`
- `jq`

## Environment setup

Create the orchestrator env file from the example:

```bash
cd apps/orchestrator
cp .env.example .env
```

Then edit `apps/orchestrator/.env` and set at least:

```env
OPENAI_API_KEY=your_real_key_here
```

Current example values are:

```env
OPENAI_API_KEY=your_openai_api_key_here
PORT=3000
PI_MODEL=openai/gpt-5.4-mini
WORKER_IMAGE=agentsofchaos/pi-worker:latest
WORKER_NETWORK=agentsofchaos-grid
WORKER_INTERNAL_PORT=3000
GRID_SIZE=4
MERGE_MODEL=gpt-5.4-mini
```

## Start the system

From the repo root:

```bash
cd apps/orchestrator
./dev-up.sh
```

What this does:

1. builds the worker image from `apps/pi-worker/Dockerfile`
2. starts the orchestrator with Docker socket access via `docker compose`

When the server is up, the orchestrator listens on:

```text
http://localhost:3000
```

Port `3000` is now API-only; the legacy static prototype UI has been removed.

## Start manually without `dev-up.sh`

If you want to run the steps directly:

```bash
cd /path/to/repo
docker build -f apps/pi-worker/Dockerfile -t agentsofchaos/pi-worker:latest .
cd apps/orchestrator
docker compose up --build
```

## Current API surfaces

The orchestrator currently exposes:

- WebSocket API at `ws://localhost:3000`
- REST API under `/api/*`
- SSE event stream at `/api/events/stream`

The legacy static browser prototype is no longer served from the orchestrator on port `3000`.

See:
- `docs/orchestrator-api.md`

## Quick health check

Check global orchestrator state:

```bash
curl http://localhost:3000/api/state
```

Expected shape:

```json
{
  "sessionId": "...",
  "model": "openai/gpt-5.4-mini",
  "mergeModel": "gpt-5.4-mini",
  "instanceCount": 0,
  "instances": []
}
```

## Create an instance via REST

```bash
curl -X POST http://localhost:3000/api/instances
```

Example response:

```json
{
  "slot": 0,
  "label": "pi-1",
  "agentUuid": "piagent_..."
}
```

## Prompt an instance via REST

```bash
curl -X POST http://localhost:3000/api/instances/0/prompt \
  -H 'Content-Type: application/json' \
  -d '{"message":"Using bash only, run exactly this shell command: cd /workspace && printf \"hello\\n\" > hello.txt && git add -A && git commit -m \"hello\" Do not just explain; execute the command."}'
```

Prompt completion should be observed through:

- SSE stream
- WebSocket events

## Watch the event stream via SSE

```bash
curl -N http://localhost:3000/api/events/stream
```

You should see events like:

- `grid_boot`
- `grid_ready`
- `instance_created`
- `session_ready`
- `session_output`
- `pi_event`
- `fork_complete`
- `merge_complete`

## Run automated verification

### Smoke test

```bash
cd apps/orchestrator
npm run e2e
```

This tests the current integration-instance merge behavior.

### Battle test

```bash
cd apps/orchestrator
npm run battle:e2e
```

This tests:

- instance creation
- prompting
- fork
- merge prep
- clean merge
- conflict merge
- stop lifecycle

## Useful artifact endpoints

After forking or merging, you can fetch artifacts such as:

### Fork point

```bash
curl http://localhost:3000/api/instances/0/artifacts/fork-point
```

### Merge details

```bash
curl http://localhost:3000/api/instances/2/artifacts/merge-details
```

### Merge context markdown

```bash
curl http://localhost:3000/api/instances/2/artifacts/merge-context
```

## Common problems

### 1. Docker not installed or not running

Symptoms:
- `docker: command not found`
- Docker build or compose fails
- worker containers do not start

Fix:
- install Docker
- start Docker daemon/service

### 2. No access to Docker socket

Symptoms:
- permission denied talking to `/var/run/docker.sock`
- orchestrator can start but cannot create workers

Fix:
- ensure Docker socket is mounted into orchestrator
- ensure your user can run Docker locally
- if needed, use `sudo docker ...` for direct local inspection

### 3. Port 3000 already in use

Symptoms:
- compose/start failure
- browser cannot reach correct app

Fix:
- stop the conflicting process
- or change `PORT` in `apps/orchestrator/.env`

### 4. Missing `OPENAI_API_KEY`

Symptoms:
- workers may still start
- merge-context generation falls back to non-model summary text
- coding behavior may fail depending on provider requirements

Fix:
- set `OPENAI_API_KEY` in `apps/orchestrator/.env`

### 5. Worker image missing or stale

Symptoms:
- worker startup errors
- old behavior after code changes

Fix:
- rerun:
  ```bash
  cd apps/orchestrator
  ./dev-up.sh
  ```
- or rebuild manually with `docker build`

## Shutdown

If running with compose in the foreground, stop with:

```bash
Ctrl+C
```

To stop containers explicitly:

```bash
cd apps/orchestrator
docker compose down
```

## Current limitations

The current setup is intentionally simple:

- single-user
- no auth
- one global orchestrator state
- slots are in-memory and process-local
- worker state is container-local
- no durable multi-user session store yet

That simplicity is intentional for the current prototype and hackathon flow.
