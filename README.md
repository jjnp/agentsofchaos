# Agents of Chaos

> Agent work isn't a conversation — it's a graph of evolving intent, context, and code.

![demo](docs/assets/demo.gif)

## What this is

Most coding-agent tools force you into a single chat thread: one mutable
memory, one opaque present state, one blurred history. Real engineering
work doesn't look like that. You branch. You try alternatives. You
backtrack. You compare. You merge.

Agents of Chaos treats agent work the way version control already treats
code: as an immutable graph of durable nodes, with three-way merges that
reconcile **both code and context** from a common ancestor.

- **Nodes are immutable.** A prompt creates a child. A retry creates a
  sibling. A merge creates an integration node. Nothing gets silently
  overwritten.
- **Runs are ephemeral.** Every run executes in a fresh git worktree and
  emits a normalized event stream. Cancel mid-flight without leaving
  zombies behind.
- **Context is a peer of code.** Goals, decisions, assumptions, open
  questions, touched files — all typed, all versioned, all merged from
  a common ancestor like a real diff.
- **Conflicts are first-class.** A merge can be `ready`,
  `code_conflicted`, `context_conflicted`, or `both_conflicted`.
  Resolution is a prompt-driven successor node, not a silent rewrite.
- **Local-first.** SQLite + your git repo. No hosted control plane, no
  per-seat license, no telemetry.

```text
              ┌──────────────┐
              │ root         │
              │ kind=root    │
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │ seed         │   shared ancestor
              └──┬────────┬──┘
                 ▼        ▼
          ┌────────┐  ┌────────┐
          │ branch │  │ branch │
          │   A    │  │   B    │
          └────┬───┘  └───┬────┘
               └────┬─────┘
                    ▼
              ┌──────────┐
              │  merge   │   code_conflicted
              └────┬─────┘
                   ▼
              ┌──────────┐
              │ resolve  │   successor node, own provenance
              └──────────┘
```

## Repo layout

| Path | Purpose |
|---|---|
| [`orchestrator/`](orchestrator/) | FastAPI daemon. Owns the graph, snapshots, runs, merges, events, artifacts. SQLite + git as substrate. Pluggable runtime adapters and sandbox backends. |
| [`frontend/`](frontend/) | SvelteKit graph-native UI. Drag-to-merge canvas, live event stream, code diffs, structured context, conflict-resolution form, artifact viewer. |
| [`docs/`](docs/) | Manifesto, architecture, context model, runtime contract, ADRs, reviews. |
| [`.pi/`](.pi/) | Project-local pi extension prompts and skills. |

## Quick start

Two processes, side-by-side.

### 1. Orchestrator daemon

```bash
cd orchestrator
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e '.[dev]'

# Optional: drop your OpenAI key into orchestrator/.env so pi inherits it.
set -a; source .env; set +a

AOC_HOST=0.0.0.0 \
AOC_RUNTIME_BACKEND=pi \
.venv/bin/python -m agentsofchaos_orchestrator.main
```

Listens on `http://127.0.0.1:8000`. All knobs are `AOC_*` env vars; see
[`orchestrator/src/agentsofchaos_orchestrator/infrastructure/settings.py`](orchestrator/src/agentsofchaos_orchestrator/infrastructure/settings.py).

### 2. Frontend

```bash
cd frontend
bun install   # or npm install
bun run dev   # or npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api/orchestrator/*`
to the daemon (override target via `ORCHESTRATOR_BASE_URL`).

## Runtime adapters

The orchestrator owns the graph; runtimes are pluggable execution
backends that consume a workspace + context snapshot, stream normalized
events, and return provenance. The graph stays the same regardless of
who executed the run.

| Adapter | Status | Notes |
|---|---|---|
| `noop` | shipped | Deterministic fixture runtime — used by the e2e suite and the demo. |
| `pi` | shipped | Spawns [`pi`](https://github.com/badlogic/pi-mono) in RPC mode. Reads provider/model from `~/.pi/agent/settings.json`, credentials from env or `~/.pi/agent/auth.json`. |
| `claude_code` | planned | Adapter slot reserved. |
| `codex` | planned | Adapter slot reserved. |

Architectural rule: **pi is the first runtime, not the architecture**.
See [`docs/runtime-adapters.md`](docs/runtime-adapters.md) and
[`docs/adrs/0005-runtime-adapters-pi-first-not-pi-only.md`](docs/adrs/0005-runtime-adapters-pi-first-not-pi-only.md).

## Sandboxing

Every runtime spawn goes through a `SandboxBackend`. Three backends ship
today; the per-runtime network default keeps LLM-using agents working
without operator gymnastics.

| Backend | Selected via | Default network | Notes |
|---|---|---|---|
| `none` | `AOC_SANDBOX_BACKEND=none` (default) | host | Direct `subprocess.exec`. Frictionless local dev. |
| `bubblewrap` | `AOC_SANDBOX_BACKEND=bubblewrap` | per-runtime (`pi`=full, `noop`=none) | Linux user-namespace sandbox. Sub-100ms startup. RW-mounts the worktree, RO-mounts `~/.pi/agent` when present. |
| `docker` | `AOC_SANDBOX_BACKEND=docker` | per-runtime | Cross-platform. Pulls `debian:stable-slim` by default; pin your own image with `AOC_SANDBOX_DOCKER_IMAGE`. |

Full design: [`docs/adrs/0010-pluggable-sandbox-layer.md`](docs/adrs/0010-pluggable-sandbox-layer.md).

## Tests

```bash
# Backend (pytest + httpx + FastAPI TestClient)
cd orchestrator && .venv/bin/python -m pytest tests/ -q

# Frontend type-check + build
cd frontend && npx svelte-check --tsconfig ./tsconfig.json && npm run build

# Frontend end-to-end (Playwright drives a real browser against a fresh
# daemon + dev-server combo — no manual setup required)
cd frontend && npm run test:e2e
```

The Playwright config provisions an isolated git fixture at
`/tmp/aoc-e2e-repo` and a clean SQLite at `/tmp/aoc-e2e.sqlite3`, then
spins up the orchestrator daemon (with `runtime_backend=noop`) and the
Vite dev server before any spec runs.

### Re-recording the demo gif

The gif at the top is generated end-to-end from a real Playwright run:

```bash
cd frontend
npx playwright test --config playwright.demo.config.ts
bash scripts/build-readme-gif.sh
```

The recording walks the canonical flow (root → prompts → drag-merge →
conflicted merge → resolution → artifacts) and `scripts/build-readme-gif.sh`
turns the resulting webm into a 2x-speed gif via two-pass ffmpeg
palette generation. Output: `docs/assets/demo.gif`.

## Architecture in one screen

* **Nodes are immutable.** Code and context snapshots are durable; a
  retry creates a sibling, a merge creates an integration node.
* **Runs are ephemeral.** They execute in temporary git worktrees,
  optionally inside a sandbox, and emit a normalized stream of
  `runtime_event`s.
* **Merges reconcile from a common ancestor** for both code (real
  three-way git merge) and context (typed section-by-section merge).
* **Conflicts are first-class.** Conflicted merges are durable nodes;
  resolution is a prompt-driven runtime flow that creates a successor.
* **The graph is the product** — not a visualization of hidden state.

Deeper docs:
- [`docs/manifesto.md`](docs/manifesto.md) — what we believe
- [`docs/architecture.md`](docs/architecture.md) — system design
- [`docs/context-model.md`](docs/context-model.md) — first-class context
- [`docs/runtime-adapters.md`](docs/runtime-adapters.md) — runtime contract
- [`docs/implementation-plan.md`](docs/implementation-plan.md) — phased build
- [`docs/adrs/`](docs/adrs/) — decision records
- [`orchestrator/AGENT.md`](orchestrator/AGENT.md) — engineering contract for the daemon package

## Hackathon

Agents of Chaos started as a hackathon project and **placed second at
the OpenAI Codex hackathon in Vienna (April 2026)**. The original
submission — Node MVP orchestrator, v1 SvelteKit frontend, pi-worker
template, prototype pi-rpc app — is preserved on branch
[`hackathon-17.04`](../../tree/hackathon-17.04). That snapshot is the
one that actually ran on the demo stage on 2026-04-17.

Everything on `main` since then is the v2 rewrite: a graph-native
Python orchestrator and a SvelteKit 2 / Svelte 5 frontend rebuilt
around the manifesto. The hackathon code is kept untouched as history,
not deleted, because the point of this whole project is that history
should be preserved by default.
