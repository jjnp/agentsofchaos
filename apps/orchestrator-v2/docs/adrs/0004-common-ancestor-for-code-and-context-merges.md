# ADR 0004: Require a common ancestor for both code and context merges

- Status: Accepted
- Date: 2026-04-24

## Context

Three-way merge semantics are essential for trustworthy code integration. The same problem exists for context: without ancestry, merged intent collapses into duplicated or contradictory summaries.

## Decision

All canonical merge operations in Agents of Chaos v2 must resolve a common ancestor and use it for:
- code merge
- context merge

The daemon must not support lineage-free canonical context merges.

## Consequences

### Positive
- merge results become interpretable
- shared inheritance is preserved
- divergent intent can be identified honestly
- conflict reporting becomes meaningful for context as well as code

### Negative
- implementation is stricter
- some “convenient” merge shortcuts are disallowed
- context merge requires more careful domain design than free-form summarization

## Notes

This decision does not forbid producing best-effort comparison summaries for UI convenience. It does forbid treating such summaries as the canonical merged context state.
