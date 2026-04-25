# ADR 0006: Defer database migrations until the 1.0 schema baseline

- Status: Accepted
- Date: 2026-04-24

## Context

Agents of Chaos is still before its first stable schema. The persistence model is evolving quickly as core concepts are clarified:

- immutable nodes
- runs
- code snapshots
- context snapshots
- artifacts
- event records
- outbox events
- future merge records

Maintaining migrations for every pre-1.0 schema adjustment would add process overhead before the schema has stabilized.

## Decision

Until the 1.0 schema baseline, this system will not maintain forward migrations for local development databases.

Pre-1.0 persistence will use SQLAlchemy metadata creation for fresh local databases.

Before 1.0, the project must:

- define the stable schema baseline
- introduce Alembic or an equivalent migration mechanism
- create an initial baseline migration
- document the supported upgrade path from the final pre-1.0 development state, if any

## Consequences

### Positive

- faster schema iteration before the core model stabilizes
- less migration churn while domain concepts are still moving
- simpler local development during early architecture work

### Negative

- pre-1.0 databases are disposable unless manually migrated
- contributors may need to delete/recreate local SQLite state after schema changes
- schema compatibility is not guaranteed before 1.0

## Guardrails

This decision does not lower the persistence quality bar.

Schema changes must still be:

- explicit in ORM/domain code
- reflected in docs when architectural concepts change
- covered by tests once dependency execution is available
- considered for the eventual 1.0 baseline

The system must not silently pretend pre-1.0 databases are upgrade-stable.

## Notes

This ADR supersedes earlier implementation-plan wording that recommended migrations from the first persistence commit.
