# ADR 0010 — Pluggable sandbox layer for runtime processes

## Status

Accepted (2026-04-25)

## Context

Today the orchestrator spawns runtime adapters (Pi, future Claude Code,
Codex, …) inside the daemon process. Whatever those adapters spawn —
the actual coding agent binary — runs as the daemon's uid against the
host filesystem and host network. There is no boundary between the
agent and:

- arbitrary files outside the worktree (`~/.ssh`, `~/.aws`, `~/.npmrc`)
- the rest of the user's git checkouts
- arbitrary outbound network endpoints
- long-running background processes that survive the run

This is acceptable for hackathon-grade local use but unacceptable as
soon as the same daemon is run against unfamiliar code, on a shared
machine, or with multiple agent vendors that have different trust
profiles.

Bubblewrap is the obvious first sandbox: namespace-based, no daemon,
no setup beyond the binary, ships in most modern Linux distros. Docker
is the obvious second: cross-platform, lets us pin agent toolchains
into images, and gives us cgroup-level resource limits for free. We
expect more (`nsjail`, `gVisor`, firecracker, qemu) over time.

## Decision

Introduce a `SandboxBackend` protocol. Backends are selected at daemon
startup via `AOC_SANDBOX_BACKEND` and injected into runtime adapters
through DI — adapters do **not** know which sandbox they are running
under, only that some process-spawn capability has been provided.

```
┌──────────────────────────────────────────┐
│  RunApplicationService                   │
│   ↓                                      │
│  RuntimeAdapter (e.g. PiRuntimeAdapter)  │
│   ↓ sandbox.run(SandboxedExecutionSpec)  │
│  SandboxBackend (none | bwrap | docker)  │
│   ↓ argv translation                     │
│  OS process                              │
└──────────────────────────────────────────┘
```

### `SandboxedExecutionSpec`

A typed spec that adapters hand to the sandbox:

| Field | Purpose |
|---|---|
| `command: tuple[str, ...]` | argv to execute |
| `cwd: Path` | working directory (must be reachable inside the sandbox) |
| `read_write_mounts: tuple[Path, ...]` | dirs the agent may write (typically the worktree) |
| `read_only_mounts: tuple[Path, ...]` | dirs the agent may read (e.g. `~/.pi/agent/` for credentials) |
| `env: dict[str, str]` | environment passed in (whitelisted; no inheritance) |
| `network: NetworkPolicy` | `full` \| `none` |
| `stdin: bytes \| None` | stdin if any |
| `cancellation_token: RuntimeCancellationToken` | propagates run cancellation |
| `timeout_seconds: float \| None` | wall-clock cap (Phase 4) |

### Backends

- **`NoSandboxBackend`** (default) — spawns directly via `asyncio.create_subprocess_exec`. Preserves the current behaviour and keeps local dev unchanged.
- **`BubblewrapSandboxBackend`** — translates the spec to `bwrap` argv: `--ro-bind /` for system; explicit `--bind` for RW mounts; `--proc /proc`; `--dev /dev`; `--unshare-net` when network is `none`; `--new-session`; `--die-with-parent`; envs passed only through `--setenv`.
- **`DockerSandboxBackend`** — `docker run --rm -v <rw>:<rw>:rw -v <ro>:<ro>:ro --network=none|host --user $(id -u):$(id -g) <image> <cmd>`. Image is configurable; default is a slim image with `git` and the host's `pi`/`claude-code`/`codex` binary mounted in.

### Adapter contract change

Adapters constructed without a sandbox keep working (we inject the
`NoSandboxBackend` by default). Adapters that spawn external processes
take a `SandboxBackend` in their constructor and route every
`subprocess.exec` call through it. The PI adapter's
`process.py` is the only current consumer.

### What is and is not protected

| Concern | Protected by sandbox |
|---|---|
| Filesystem read outside RO/RW mounts | ✅ |
| Filesystem write outside RW mounts | ✅ |
| Outbound network when `network=none` | ✅ (bwrap, docker) |
| Resource exhaustion | partial (docker only, Phase 4 for cgroup-v2 on bwrap) |
| Kernel exploits | ❌ (use docker for stronger isolation, or future gVisor/firecracker) |
| Git merge worktrees (run by the daemon, not by an agent) | ❌ — out of scope |
| Daemon itself | ❌ — daemon is trusted code |

### Credentials

Some agents need credentials (Pi reads `~/.pi/agent/auth.json` and
`OPENAI_API_KEY`). The sandbox spec has explicit hooks for this: a
read-only mount of the credentials directory and an env whitelist. The
runtime adapter declares what it needs; the sandbox layer enforces the
whitelist.

## Consequences

**Positive**:
- Adapters don't need per-backend sandbox code.
- New backends are additive — drop in another `SandboxBackend` impl.
- Default `none` keeps local dev frictionless; opting into `bubblewrap`
  is a one-env-var flip.
- Settings-level config means the same adapter binary runs differently
  across `dev`, `staging`, and `prod` profiles.

**Negative**:
- Cross-platform parity is imperfect: bwrap is Linux-only, so macOS
  developers either run with `none` (less safe) or pay docker latency.
- Process startup gets slower (especially docker; bwrap is sub-100ms).
- Some agent toolchains assume host tools (node, ripgrep, …) — those
  must be on the sandbox image or on the bwrap RO mounts, otherwise
  agents fail in confusing ways.

**Trade-offs we accept**:
- We do not go straight to gVisor/firecracker. Bubblewrap and docker
  cover ~95% of the realistic threat surface (unintended writes,
  credential exfiltration, accidental network calls) at a fraction of
  the operational cost.
- `--unshare-net` blocks DNS too, which means agents that try to clone
  random repos will fail loudly. That is the desired behaviour for
  `network=none` profiles.

## Future work

- gVisor / nsjail / firecracker backends.
- Per-mount overlayfs so the agent can mutate a temp filesystem and we
  diff what changed at the end of the run.
- Sandbox-level audit log: every spawn the agent attempts, what it
  read, what it wrote. Streamed into the existing event bus.
- Sandboxed git merge worktrees once we add second-class runtimes that
  participate in merges.
