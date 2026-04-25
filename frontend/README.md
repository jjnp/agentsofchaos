# frontend

Browser graph UI for the Agents of Chaos orchestrator daemon.

Speaks the graph-native API — no compatibility with the hackathon Node MVP (`apps/orchestrator/`) or the v1 frontend (`frontend/`).

## Stack

- SvelteKit 2 + Svelte 5 (runes)
- Tailwind CSS 4
- Vite 8 + Vitest
- TypeScript strict
- valibot for schema-derived types
- bun as package manager

## Getting started

```bash
bun install
bun run dev
```

Defaults to proxying orchestrator calls to `http://127.0.0.1:8000` (set `ORCHESTRATOR_BASE_URL` to override).

Start the daemon separately:

```bash
cd ../orchestrator
python3 -m agentsofchaos_orchestrator.main
```

## Scope (round 1)

Covers the backend features that exist today:

- open project → `POST /projects/open`
- see graph → `GET /projects/{id}/graph`
- inspect node (code snapshot id, context snapshot id, originating run)
- prompt from node → `POST /projects/{id}/nodes/{id}/runs/prompt`
- live updates → SSE `/projects/{id}/events/stream`

Waits on backend:

- code/context diff viewer (no diff endpoints yet)
- merge UI (Phase 5)
- run cancel
- context snapshot detail (no single-snapshot GET endpoint yet)
