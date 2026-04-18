# agentsofchaos

A novel graph-based interface for coding agents that makes branching, parallel exploration, and mergeable reasoning paths visible and interactive, so users can steer Pi-like agent workflows more directly.

This repo now contains two demos:

- `apps/pi-rpc/` — the earlier single-container, multi-process prototype
- `apps/orchestrator/` + `apps/pi-worker/` — the new Docker-orchestrated version with **one container per pi instance**

## Recommended demo: Docker orchestration + forking

The current main demo is a **2×2 grid of pi workers**, where:

- each tile is its own **Docker container**
- each worker runs a single `pi --mode rpc` instance
- the browser talks to an **orchestrator** service
- the orchestrator creates/removes worker containers over the Docker API
- a worker can be **forked** into another slot using Docker `commit`, so the child inherits filesystem + pi session state from the parent snapshot

This is the Level 2 model we discussed:

- snapshot/fork **filesystem + pi state**
- do **not** try to snapshot live process RAM
- lean on Docker overlay/layer behavior instead of copying bind-mounted workspaces
- worker images start with a baked-in snapshot of the repo, then diverge in each container's writable layer

## Layout

- `apps/orchestrator/` — browser UI + Docker orchestration service
- `apps/pi-worker/` — single-worker image that exposes a websocket bridge around `pi --mode rpc`
- `apps/pi-rpc/` — older all-in-one prototype kept around for reference

Worker containers now keep state in fixed in-container paths:

- `/workspace` — git repo state
- `/state/pi-agent` — pi session/state files
- `/state/meta` — future lineage/merge metadata

## Run the orchestrated demo

For a fuller setup guide, see:
- `docs/setup.md`

From the repo root:

```bash
cd apps/orchestrator
./dev-up.sh
```

That script:

1. builds `agentsofchaos/pi-worker:latest`
2. starts the orchestrator with Docker socket access

Then open:

```text
http://localhost:3000
```

For an automated smoke test when Docker is available:

```bash
cd apps/orchestrator
npm run e2e
```

## Features in the orchestrated demo

- 2×2 grid of running pi instances
- prompt each instance separately
- broadcast prompt to all instances
- abort per instance or all at once
- terminal-style output per instance
- fork one instance into another slot via Docker snapshot image
- prepare merge input from one instance into another via `git bundle create` + import/fetch inside the target container
- execute a full merge flow: checkpoint dirty trees, export bundle from source, fetch+merge in target, then write AI-generated merged context to `/state/meta/merge-context.md`

## Environment

Main env file for the orchestrated demo:

- `apps/orchestrator/.env`

Current default model:
- `openai/gpt-5.4-mini`

Template:

- `apps/orchestrator/.env.example`

The `.env` file is gitignored. Because the API key was shared in chat, rotate it after testing.

## Notes

- The orchestrator uses the Docker socket, so treat it as privileged.
- Worker containers are ephemeral and are removed when the browser websocket disconnects.
- Fork snapshots are also cleaned up when the session ends.
- Workers receive secrets like `OPENAI_API_KEY` via environment variables, not baked into the image.
- Workers now persist pi sessions under `/state/pi-agent` because they no longer run with `--no-session`.
- The orchestrator now has Docker-exec based helpers for git status, checkpoint commits, git bundle export/import, merge execution, latest-session extraction, and AI-generated merge context writing.
- Docker is required on the host. I could not test Docker orchestration on this VM because the Docker CLI/socket is not available here.
