# ADR 0003: Treat context as a first-class durable model

- Status: Accepted
- Date: 2026-04-24

## Context

Prototype-era systems often treat context as a hidden agent session, a transcript, or a free-form summary. That is not sufficient for a graph system whose core value is preserving and merging lines of work.

## Decision

Every node in Agents of Chaos v2 will carry:
- a **code snapshot**
- a **context snapshot**

Context snapshots are typed, durable, inspectable, and diffable.
They are not equivalent to raw transcripts.

Raw transcripts and event logs remain important provenance, but the canonical context model is a structured snapshot derived from that provenance.

## Consequences

### Positive
- context becomes inspectable in the UI
- branch intent and handoff become durable
- context diff and merge become possible
- the system can model work, not just files

### Negative
- more domain modeling work is required up front
- projection and merge logic become richer and must be tested carefully

## Notes

The initial context schema may be minimal, but it must still be explicit, typed, and versioned.
