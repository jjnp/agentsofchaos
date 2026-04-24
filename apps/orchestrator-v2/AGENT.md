# AGENT.md

This file defines the engineering contract for `apps/orchestrator-v2/`.

Anyone implementing code in this folder must follow it.

## 1. Mission

Build a **local-first, high-trust, immutable graph daemon** for Agents of Chaos v2.

The daemon must model:

- immutable nodes
- ephemeral runs
- first-class code snapshots
- first-class context snapshots
- ancestor-based merges for both code and context
- precise provenance
- a browser-facing API that is simple, typed, and explicit

## 2. Non-negotiable product invariants

These are architectural laws, not suggestions.

### 2.1 The graph is primary
The graph is the product. The backend exists to serve a durable graph of work, not to hide mutable state behind a REST API.

### 2.2 Nodes are immutable
Once created, a node's code snapshot and context snapshot must never be mutated in place.

Allowed post-creation updates are limited to light metadata such as:
- display title
- labels / tags
- cached derived summaries

### 2.3 Runs are ephemeral
Execution is temporary. Durable state belongs to nodes, context snapshots, artifacts, and event records.

### 2.4 Context is first-class
Context is not an implementation detail of an agent adapter. It must be modeled, stored, diffed, and merged explicitly.

### 2.5 Merges require a common ancestor
Code merges and context merges must both reconcile from a common ancestor. No naive “blend the latest two states” shortcuts are allowed.

### 2.6 Provenance is mandatory
Derived state must retain provenance. If the system cannot explain where a context item, summary, or merge artifact came from, the design is incomplete.

## 3. Engineering bar

This implementation is expected to be **engineering-grade**.

That means:

- explicit architecture
- strict typing
- small, testable units
- deterministic behavior where possible
- crisp IO boundaries
- documented invariants
- excellent tests
- careful failure handling
- no “just for now” hidden debt

If a shortcut is taken, it must be documented as a deliberate tradeoff with a clear removal plan.

## 4. Code quality rules

### 4.1 Type discipline
- Python 3.12+ only.
- `mypy --strict` must pass.
- Avoid `Any`. Treat `Any` as a code smell.
- Avoid unchecked `cast()` unless the invariant is documented locally.
- Use `typing.Final`, `Literal`, `NewType`, `Protocol`, and frozen dataclasses where they improve correctness.
- Prefer value objects and typed domain models over ad hoc dictionaries.

### 4.2 API boundaries
- External IO must be validated explicitly.
- Use Pydantic models for API DTOs and settings.
- Keep domain models separate from transport DTOs and ORM models.
- Do not leak ORM objects through service or API boundaries.

### 4.3 Domain modeling
- Prefer explicit domain types over strings scattered through the codebase.
- Statuses, operation kinds, conflict kinds, and artifact kinds must be enums or equivalent typed constants.
- Important identifiers should use distinct types or wrappers where practical.

### 4.4 Purity and side effects
- Keep pure logic pure.
- Isolate side effects in infrastructure adapters.
- Domain logic must not directly shell out, hit the filesystem, or call network services.
- Git, filesystem, agent runtime, and model integrations must sit behind typed interfaces.

### 4.5 Errors
- Never swallow exceptions silently.
- Use explicit domain errors for expected failure cases.
- Preserve context in logs and raised errors.
- Fail loudly on invariant violations.

### 4.6 Logging
- Use structured logging.
- Logs must be helpful for debugging concurrency, runs, merges, and reconciliation.
- Never log secrets.

## 5. Architecture rules

### 5.1 Layering
Code should be organized into clearly separated layers:

- `domain/` — invariants, value objects, entities, domain services, domain errors
- `application/` — orchestrating use cases, transactions, coordination
- `infrastructure/` — database, git, filesystem, runtime adapters, persistence, logging
- `api/` — FastAPI routes, DTOs, SSE/WebSocket transport

Dependencies must point inward.

### 5.2 No mega-files
No file should become the new `server.js`.
If a file feels like “the place where everything happens,” split it.

### 5.3 Git service boundary
All git operations must go through a dedicated service boundary with typed inputs and outputs.
Do not spread raw subprocess git calls throughout the codebase.

### 5.4 Context service boundary
Context projection, context diffing, and context merging must be explicit modules. Do not bury context logic inside run orchestration code.

### 5.5 Runtime adapter boundary
The daemon must not be tightly coupled to one agent implementation. Define a runtime adapter protocol and implement the first adapter against it.

## 6. Testing standards

### 6.1 Test pyramid
Use a balanced mix of:
- unit tests for pure logic
- service tests for application workflows
- adapter tests for infrastructure boundaries
- integration tests for git/worktree/database flows

### 6.2 Required test coverage by concern
The following must be tested aggressively:
- node immutability invariants
- common-ancestor resolution
- context merge semantics
- conflict classification
- run lifecycle transitions
- recovery and cleanup of failed runs
- repository/worktree safety boundaries

### 6.3 Determinism
- Pure merge logic should be deterministic.
- Tests should not rely on wall-clock timing unless unavoidable.
- Time, UUID generation, and filesystem roots should be injectable in tests.

### 6.4 No untested critical logic
Critical logic without tests is not done.
This includes merge code, reconciliation logic, migrations, and repository mutation flows.

## 7. Documentation standards

### 7.1 Docs are part of the system
If architecture changes, docs must change in the same branch.

### 7.2 Write for maintainers
Docs should explain:
- what invariant exists
- why it exists
- how it is enforced
- where it is tested

### 7.3 ADRs
Any material architectural decision should be written as an ADR in `docs/adrs/`.

## 8. Git and change management

### 8.1 Commits
- Make small, coherent commits.
- Commit messages should explain intent, not just mechanics.
- Do not mix refactors, behavior changes, and formatting churn in one commit.

### 8.2 Branches / PRs
- One focused branch per change.
- Open PRs with clear problem statements and validation notes.
- If a design changes an invariant, update the relevant doc and ADR in the same PR.

### 8.3 Reviewability
Before 1.0, large architectural refactors are allowed when they build a stronger long-term foundation.

Even then, optimize for architectural clarity rather than churn.
A reviewer should be able to answer:
- what changed
- why it changed
- what invariant it affects
- how it was tested
- whether the new foundation is simpler and more durable than the old one

## 9. Security and safety

- Never interpolate untrusted values into shell strings.
- Prefer subprocess argument lists to shell execution.
- Constrain filesystem writes to daemon-owned directories.
- Be explicit about repository boundaries.
- Never trust agent output as safe to execute.
- Keep secrets out of logs, artifacts, fixtures, and tests.

## 10. Performance principles

- Correctness first.
- Simplicity second.
- Performance third, but measured.

When optimization is needed:
- measure first
- optimize the hot path only
- keep invariants obvious

## 11. Forbidden shortcuts

The following are not acceptable without an explicit ADR and justification:

- mutating node snapshots in place
- merging context without a common ancestor
- treating raw transcripts as the canonical context model
- spreading git subprocess calls throughout the codebase
- using untyped dictionaries for core domain state
- relying on hidden global state for coordination
- embedding product rules directly in route handlers
- landing failing type checks or tests

## 12. Definition of done

A change is done only when:

- the design still respects the core invariants
- the code is typed and readable
- the tests are sufficient and passing
- docs are updated if behavior or architecture changed
- the change is reviewable and well-scoped
- no known invariant-breaking debt is left undocumented

## 13. Default decision rule

When in doubt, prefer the option that is:

1. more explicit
2. more typed
3. easier to test
4. more faithful to graph/code/context immutability
5. easier to reason about six months from now

Do not optimize for cleverness.
Optimize for trust.
