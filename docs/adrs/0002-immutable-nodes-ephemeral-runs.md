# ADR 0002: Model durable work as immutable nodes and execution as ephemeral runs

- Status: Accepted
- Date: 2026-04-24

## Context

The prototype mixed durable graph semantics with mutable long-lived workers. That made the demo possible, but it left ambiguity around what exactly a node represented at any given moment.

The graph itself is the product and must be trustworthy.

## Decision

Agents of Chaos will model:
- **nodes** as immutable durable snapshots of work
- **runs** as ephemeral execution attempts that start from a node and may produce a child node

Prompting a node does not mutate it in place.
Retrying creates a sibling.
Merging creates an integration node.

## Consequences

### Positive
- stronger historical clarity
- easier comparison of sibling attempts
- cleaner merge semantics
- better fit for graph-native UX
- simpler reasoning about provenance

### Negative
- more nodes in the graph
- UI will need filtering, collapsing, and summary affordances
- some users may need to adapt from mutable-session mental models

## Notes

Immutability applies to code and context snapshots. Light metadata updates remain allowed where they do not alter durable work identity.
