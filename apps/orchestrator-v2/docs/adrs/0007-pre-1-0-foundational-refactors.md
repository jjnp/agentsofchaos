# ADR 0007: Allow foundational refactors before 1.0

- Status: Accepted
- Date: 2026-04-24

## Context

Agents of Chaos v2 is still before its 1.0 architecture baseline. The goal of the pre-1.0 phase is not API or implementation stability. The goal is to build a foundation that can last.

Some early internal shapes will be wrong or incomplete. Preserving them for short-term reviewability would create worse long-term debt.

## Decision

Before 1.0, large architectural refactors are allowed when they materially improve the long-term foundation.

This includes refactors that:
- split application services
- replace direct repository usage with unit-of-work boundaries
- revise event/outbox architecture
- move context projection behind explicit services
- reshape runtime adapter internals
- change disposable pre-1.0 database schema

## Guardrails

Large refactors must still preserve core product invariants:
- nodes remain immutable
- runs remain ephemeral
- context remains first-class
- code and context merges require common ancestors
- runtime-specific details do not leak into canonical graph semantics

Large refactors must also leave the codebase in a coherent state:
- compileable
- typed by design
- organized by stable boundaries
- documented when architecture changes
- free of known invariant-breaking debt

## Consequences

### Positive

- permits necessary foundational redesign before public stability
- avoids calcifying bad early abstractions
- favors architecture that can survive beyond prototype work

### Negative

- pre-1.0 diffs may be large
- local branches may become harder to rebase
- contributors should expect churn until the 1.0 baseline

## Notes

After 1.0, this policy should tighten. Stability, migration compatibility, and review granularity should become stronger constraints once the architecture baseline is declared.
