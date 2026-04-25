# Agents of Chaos

> Agent work isn't a conversation — it's a graph of evolving intent, context, and code.

A **graph-native** interface for coding agents. Each node is a durable unit
of work — a code snapshot + a context snapshot + an execution record.
Nodes are immutable; runs are ephemeral; merges reconcile both code **and**
context from a common ancestor, just like git.

```text
                 ┌──────────────┐
            ┌────┤ root         │
            │    │ kind=root    │
            │    └──────────────┘
            │
   ┌────────┴────────┐
   ▼                 ▼
┌────────┐       ┌────────┐
│ branch │       │ branch │
│   A    │       │   B    │
└────┬───┘       └───┬────┘
     │               │
     └──────┬────────┘
            ▼
      ┌──────────┐
      │  merge   │
      │ integ.   │
      └──────────┘
```

## Repo layout

| Path | Purpose |
|---|---|
| [`orchestrator/`](orchestrator/) | Local-first FastAPI daemon. Owns the graph, code/context snapshots, runs, merges, events. SQLite + git as substrate. Pluggable runtime adapters. |
| [`frontend/`](frontend/) | SvelteKit graph-native UI. Drag-to-merge canvas, node inspector with live runtime output, code diffs, structured context. |
| [`docs/`](docs/) | Manifesto, architecture, context model, runtime contract, implementation plan, ADRs, reviews. |
| [`.pi/`](.pi/) | Project-local pi extension prompts and skills. |

The previous hackathon stack (Node MVP orchestrator + v1 SvelteKit
frontend) is preserved on branch [`hackathon-17.04`](#archive).

## Quick start

Run two processes side-by-side.

### 1. Orchestrator daemon

```bash
cd orchestrator
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e '.[dev]'

# Optional: drop your OpenAI key into orchestrator/.env
# (see below). Sourcing it makes pi inherit the credentials.
set -a; source .env; set +a

AOC_HOST=0.0.0.0 \
AOC_RUNTIME_BACKEND=pi \
.venv/bin/python -m agentsofchaos_orchestrator.main
```

Listens on `http://127.0.0.1:8000`. Configurable via `AOC_*` env vars;
see [`orchestrator/src/agentsofchaos_orchestrator/infrastructure/settings.py`](orchestrator/src/agentsofchaos_orchestrator/infrastructure/settings.py).

### 2. Frontend

```bash
cd frontend
bun install   # or npm install
bun run dev   # or npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api/orchestrator/*`
to the daemon (override target via `ORCHESTRATOR_BASE_URL`).

## Pi runtime

The default runtime adapter spawns [`pi`](https://github.com/badlogic/pi-mono)
in RPC mode against your worktree. Pi handles the LLM call, tool use, and
file edits; the orchestrator captures events, transcripts, and the
resulting commit.

Pi reads its provider/model from `~/.pi/agent/settings.json` and
credentials from environment or `~/.pi/agent/auth.json`. To use plain
OpenAI with the project's `orchestrator/.env`:

```jsonc
// ~/.pi/agent/settings.json
{ "defaultProvider": "openai", "defaultModel": "gpt-5.4-mini" }
```

```dotenv
# orchestrator/.env
OPENAI_API_KEY=sk-...
```

Other runtimes (`noop`, `claude_code`, `codex`) are first-class in the
adapter protocol; only `noop` and `pi` ship today.

## Tests

```bash
# Backend (unit + HTTP-level integration via FastAPI TestClient)
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
Vite dev server before the spec runs.

## Architecture in one screen

* **Nodes are immutable.** Code and context snapshots are durable; a
  retry creates a sibling, a merge creates an integration node.
* **Runs are ephemeral.** They execute in temporary git worktrees and
  emit a normalized stream of `runtime_event`s.
* **Merges reconcile from a common ancestor** for both code (real
  three-way git merge) and context (typed section-by-section merge).
* **The graph is the product** — not a visualization of hidden state.

Deeper docs:
- [`docs/manifesto.md`](docs/manifesto.md) — what we believe
- [`docs/architecture.md`](docs/architecture.md) — system design
- [`docs/context-model.md`](docs/context-model.md) — first-class context
- [`docs/runtime-adapters.md`](docs/runtime-adapters.md) — runtime contract
- [`docs/implementation-plan.md`](docs/implementation-plan.md) — phased build
- [`docs/adrs/`](docs/adrs/) — decision records
- [`docs/review-2026-04-24-smells.md`](docs/review-2026-04-24-smells.md) — post-integration review (mid-resolution)
- [`docs/review-2026-04-25-orchestrator-functional-gaps.md`](docs/review-2026-04-25-orchestrator-functional-gaps.md) — backend functional gap review
- [`docs/continuation-guidance-2026-04-25.md`](docs/continuation-guidance-2026-04-25.md) — handoff guidance for continuing orchestrator work
- [`orchestrator/AGENT.md`](orchestrator/AGENT.md) — engineering contract for the daemon package

## Archive

The hackathon snapshot — Node MVP orchestrator, v1 SvelteKit frontend,
pi-worker template, prototype pi-rpc app — lives on branch
[`hackathon-17.04`](../../tree/hackathon-17.04). This is the snapshot
that ran on 2026-04-17 and powered the original demo.
