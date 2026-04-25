# ADR 0001: Build as a local-first daemon

- Status: Accepted
- Date: 2026-04-24

## Context

The prototype proved the browser graph UX and the value of branch/merge semantics, but the backend architecture was optimized for hackathon speed rather than long-term trust.

A cloud-first or container-first rewrite would add substantial operational complexity before the core model is stabilized.

## Decision

Agents of Chaos will be implemented as a **local-first Python daemon**.

The daemon will:
- run on the developer’s machine
- manage a local repository directly
- persist durable state in SQLite
- expose a local API for the browser UI
- use local git and temporary worktrees as the primary execution substrate

## Consequences

### Positive
- simpler execution model
- easier debugging
- lower latency
- stronger user ownership and transparency
- less orchestration complexity in the critical early design phase

### Negative
- weaker isolation than sandbox-per-node systems
- hosted collaboration is deferred
- remote execution becomes a later concern rather than a first implementation target

## Notes

This decision does not forbid future remote runtimes.
It only says remote execution must serve the graph model rather than define it.
