# Agents of Chaos v2 Manifesto

## Coding agents should not feel like amnesia in a chat box.

Agents of Chaos v2 begins with a simple belief:

**agent work is not a conversation. It is a graph of evolving intent, context, and code.**

A linear chat hides the truth of how real work happens:
- we branch
- we try alternatives
- we backtrack
- we compare
- we merge
- we preserve partial understanding
- we carry context forward

Software development already has the right shape for this: **version control**.
Agent systems should inherit that shape, not fight it.

## We believe the graph is the product.

The graph is not a visualization of hidden backend state.
The graph is not a decoration on top of a session model.

**The graph is the primary interface.**

Each node is a real unit of work:
- a snapshot of code
- a snapshot of context
- a record of execution
- a durable point in lineage
- a thing that can be inspected, compared, forked, and merged

A node is not a temporary process.
A node is not “whatever the agent currently remembers.”
A node is a durable fact.

## We reject the tyranny of the single thread.

Most agent tools force users into one long mutable stream:
- one thread
- one memory
- one opaque present state
- one blurred history

This is the wrong abstraction.

Real implementation is non-linear.
Real thinking is non-linear.
Real collaboration is non-linear.

**Agents of Chaos v2 embraces non-linearity as a first principle.**

Every meaningful action can create a new branch of work.
Every branch remains available.
Every branch can be compared against its siblings.
Every merge creates a new integration node instead of erasing history.

## Nodes are immutable. Runs are ephemeral.

We separate durable work from temporary execution.

A **node** is immutable.
A **run** is ephemeral.

This means:
- prompting a node creates a child, not a mutation
- retrying creates a sibling, not an overwrite
- merging creates an integration node, not an in-place modification
- history is preserved by default

When a user looks at a node, they should know:

**this is what existed at that point in the graph.**

## Context is a first-class citizen.

Code alone is not enough.

Agent work depends on:
- goals
- constraints
- assumptions
- decisions
- open questions
- risks
- files explored
- handoff notes
- reasoning distilled into usable form

In v2, context is not hidden in transcripts, buried in tool logs, or left implicit in a model’s temporary memory.

**Context is durable, structured, inspectable, and versioned.**

Every node carries:
- a code snapshot
- a context snapshot

Both matter.
Both evolve.
Both can branch.
Both can merge.

## Context merges must respect ancestry.

A merge is not “combine whatever the two latest states say.”

That is true for code, and it is true for context.

When two branches merge, both code and context must reconcile from a **common ancestor**.

This means:
- code uses real three-way merge semantics
- context uses real ancestor-based reconciliation
- the system preserves what was shared
- highlights what diverged
- surfaces what conflicts

We reject summary soup.
We reject fake continuity.
We reject lineage-free synthesis.

**A merge is only meaningful if ancestry is respected.**

## Provenance matters.

Trust requires traceability.

Every context item, summary, artifact, and merge result should be grounded in provenance:
- what run produced it
- what node it belongs to
- what artifacts support it
- what ancestor it descends from

The goal is not magical autonomy.
The goal is legible agency.

## Local-first is a feature, not a compromise.

The core experience of agentic software development should run close to the developer:
- near the repository
- near the filesystem
- near the tools
- near the user’s attention

Agents of Chaos v2 is local-first because:
- speed matters
- ownership matters
- transparency matters
- debugging matters
- trust matters

Cloud and remote execution may exist later.
But they should serve the graph, not define it.

## Git is part of the ontology.

Git already understands:
- ancestry
- branches
- merges
- snapshots
- diffs
- integration

We do not want to imitate these ideas in memory.
We want to build on them honestly.

In v2:
- code snapshots are real snapshots
- branches are real lineage
- merges are real merges
- diffs are real comparisons

But git alone is not enough.
We add what git does not natively capture:
- structured context
- agent execution history
- semantic handoff
- graph-native interaction

## The user should be able to see thought become work.

Agent systems often hide the most important things:
- what the agent is doing
- what it has learned
- why it changed direction
- what it carried forward
- what it left unresolved

We want the opposite.

Users should be able to:
- watch runs live
- inspect branch context
- compare sibling attempts
- see what a merge integrated
- understand conflicts in both code and context
- continue from any point with confidence

The system should not merely execute.
It should make execution intelligible.

## Conflict is not failure.

A merge may produce:
- clean code + clean context
- clean code + conflicted context
- conflicted code + clean context
- both conflicted

This is not an edge case to hide.
It is part of real work.

By making conflicts visible and explicit, we turn them into collaboration surfaces.

## We are building for branching minds.

There is rarely one obvious next step.
Retries are valuable.
Discarded work can become future context.
Integration is creative, not clerical.

The future of coding agents is not a better chat transcript.
It is a **workspace for branching, persistent, mergeable machine collaboration**.

## What v2 stands for

Agents of Chaos v2 stands for:

- **graphs over threads**
- **nodes over sessions**
- **immutability over hidden mutation**
- **context as a peer of code**
- **ancestor-based merges over naive synthesis**
- **provenance over vibes**
- **local-first execution over opaque orchestration**
- **legibility over illusion**
- **real branching work over linear theater**

## Our promise

We want a system where you can say:

- “show me every path we explored”
- “compare these two attempts”
- “what context did this branch inherit?”
- “what changed in code and in intent?”
- “merge these from their common ancestor”
- “let me continue from here without losing anything”

And the system can answer honestly.

That is Agents of Chaos v2.

**Not a chat.
Not a black box.
A living graph of code and context.**
