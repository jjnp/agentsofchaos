# ADR 0005: Use pluggable runtime adapters with pi as the first rich runtime

- Status: Accepted
- Date: 2026-04-24

## Context

Pi is a strong first runtime for Agents of Chaos because it already provides:
- persistent sessions
- session forking
- RPC streaming
- extensions
- skills
- prompt templates
- compaction hooks
- provider and model routing

At the same time, the product must leave room for future runtimes such as Claude Code and Codex.

## Decision

Agents of Chaos will use a runtime adapter architecture.

- The AoC core remains runtime-agnostic.
- Pi is the first implemented runtime adapter.
- Pi-specific capabilities are exploited inside pi-specific adapter and projector code, not in the core graph model.
- Future adapters for Claude Code, Codex, and other runtimes must be possible without redefining nodes, code snapshots, context snapshots, or merge semantics.

## Consequences

### Positive
- high leverage from pi in the near term
- no lock-in to pi-specific concepts in the core domain
- clearer future path for multi-runtime graphs
- runtime-specific context extraction can evolve independently

### Negative
- adapter and projection boundaries require more discipline up front
- some pi-specific affordances cannot be assumed globally
- normalized event and provenance models must be designed carefully

## Notes

Runtime transcripts and session artifacts are evidence.
Canonical context snapshots remain AoC-owned projections derived from runtime provenance.
