# Runtime Adapters

This document defines how Agents of Chaos integrates with agent runtimes.

## 1. Core rule

Agents of Chaos owns the canonical:
- graph
- node lineage
- code snapshots
- context snapshots
- merge semantics
- browser-facing API

Agent runtimes do **not** own those things.

They are execution backends that:
- consume a workspace snapshot and context snapshot
- execute a run
- emit streamable provenance
- return artifacts that AoC can normalize

## 2. Why this layer exists

We want to extract the maximum value from pi now **without** coupling the product to a single runtime forever.

the system must leave room for:
- pi
- Claude Code
- Codex
- future custom runtimes

Therefore:
- **pi is the first runtime adapter**
- pi is **not** the architecture

## 3. Runtime neutrality at the core

The core domain must not depend on runtime-specific concepts such as:
- pi queue modes
- pi extension internals
- Claude-specific transcript objects
- Codex-specific transport payloads

The core only reasons about:
- source node
- source code snapshot
- source context snapshot
- run intent
- normalized run events
- normalized provenance
- resulting child node
- resulting context projection

## 4. Runtime adapter responsibilities

Every runtime adapter must provide a normalized execution contract.

Minimum responsibilities:
- start a run from a workspace path, context snapshot, and prompt
- stream normalized lifecycle and content events
- accept a runtime-neutral cancellation token
- persist or expose transcript/provenance artifacts
- report terminal status
- expose enough evidence for AoC context projection
- expose a cheap `probe()` that verifies host-side prerequisites (binary
  on PATH, credentials present, daemon reachable, …). The orchestrator
  calls it at startup to fail loudly on misconfiguration and on every
  `GET /health/runtime` request so monitoring catches drift after boot
  without a daemon restart. Failures must raise with a specific,
  operator-actionable message — not a generic boolean

Non-responsibilities:
- node creation policy
- graph persistence
- merge semantics
- canonical context merge
- browser API decisions

## 5. Runtime capabilities

Not every runtime will be equally capable.

The adapter layer models capabilities explicitly rather than assuming all runtimes look like pi.

Initial runtime-neutral capabilities include:
- RPC/event streaming
- cancellation
- persistent runtime sessions
- session clone/fork
- steering
- follow-up messages
- custom tools
- image input
- model switching

The system should support both:
- **rich runtimes** like pi
- **thin runtimes** that only support prompt/stream/finish

Capabilities are advertised by adapters and must not become hidden assumptions in core graph logic.

## 6. Pi as the first rich runtime

Pi is the first implementation target because it already provides strong primitives:
- persistent sessions
- session forking
- RPC event streaming
- extension hooks
- skills
- prompt templates
- compaction hooks
- model/provider routing

AoC should use these capabilities aggressively, but only inside the `PiRuntimeAdapter` and related pi-specific projection code.

## 7. Runtime-specific provenance vs canonical context

Runtime artifacts are evidence.
Canonical context snapshots are AoC-owned projections.

That distinction is non-negotiable.

### Runtime-specific provenance examples
For pi:
- session JSONL file
- session id
- compaction entries
- branch summary entries
- extension custom entries
- RPC event stream

For other runtimes:
- transcript export
- structured trace
- tool call log
- provider metadata

### Canonical AoC context
AoC projects runtime evidence into its own typed context model:
- goals
- constraints
- decisions
- assumptions
- open questions
- todos
- risks
- handoff notes
- read files
- touched files
- symbols

This allows nodes created by different runtimes to remain comparable and mergeable.

## 8. Cross-runtime graph is a feature

The graph model must support workflows such as:
- a root node created and extended with pi
- a sibling branch continued with Claude Code
- another sibling explored with Codex
- later comparison and integration of those branches in one graph

This only works if:
- code snapshots remain git-native and runtime-independent
- context snapshots remain AoC-native and runtime-independent
- runtime transcripts remain provenance, not canonical merged truth

## 9. Recommended adapter structure

There should be:

### 9.1 Runtime adapter protocol
A Python protocol or abstract interface defining the normalized execution contract.

### 9.2 Runtime-specific implementations
Separate implementations such as:
- `PiRuntimeAdapter`
- `ClaudeCodeRuntimeAdapter`
- `CodexRuntimeAdapter`

### 9.3 Runtime-specific context projectors
Separate projection modules such as:
- `PiContextProjector`
- `ClaudeCodeContextProjector`
- `CodexContextProjector`

These projectors translate runtime evidence into the AoC context schema.

## 10. Pi integration guidance

For the pi integration specifically:
- prefer persistent sessions by default
- use session forking for child-node creation where appropriate
- use extensions as the bridge between pi runtime internals and AoC structured provenance
- use project-local pi resources (`.pi/`) where they improve execution quality
- use RPC first; leave room for a future SDK-backed sidecar if RPC becomes limiting

## 11. What must remain runtime-agnostic

The following must remain independent of any specific runtime:
- node identity
- node immutability
- code snapshot identity
- context snapshot identity
- merge ancestry
- context merge rules
- conflict classification
- graph API semantics

## 12. Design consequence

The correct design sentence is:

> Agents of Chaos owns the canonical graph, code snapshots, and context snapshots. Agent runtimes are pluggable execution backends that produce normalized provenance and child nodes.

That is the contract future implementation must preserve.
