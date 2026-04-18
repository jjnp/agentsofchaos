# Agentsofchaos Notes

## Core idea

Build a browser-based coding playground where each agent instance runs in its own Docker container and can be:

- created on demand
- prompted independently
- forked from stable checkpoints
- merged back using Git-native primitives
- later summarized/compacted at the conversation level with AI

The product direction is not just “chat with one coding agent”, but:

- branch agent work like code branches
- compare alternative implementations
- merge successful ideas back together
- preserve lineage across filesystem state and agent context

In short:

**agents as forkable, mergeable software branches**.

---

## What we built

We built a working prototype with:

- a Node.js orchestrator
- a browser UI
- one Docker container per running pi instance
- pi running in RPC mode inside each worker container
- fork implemented via Docker snapshot images
- merge implemented via Git bundle export/import plus real `git merge`
- merge-context output written back into the instance state

This is already beyond a mockup: the prototype creates real branches, runs real containers, and reaches real merge conflicts when branches overlap.

---

## High-level architecture

### 1. Orchestrator

Location:
- `apps/orchestrator/`

Responsibilities:
- serves the frontend
- manages browser websocket sessions
- creates and stops worker containers over Docker API
- routes prompts to specific workers
- performs fork operations
- performs merge preparation and merge execution
- extracts session context from workers
- uses OpenAI to summarize merge context

Tech:
- Node.js
- `dockerode`
- `ws`
- `openai`
- `tar-stream`

### 2. Worker

Location:
- `apps/pi-worker/`

Responsibilities:
- runs a single `pi --mode rpc` instance
- exposes a websocket bridge to the orchestrator
- streams assistant/tool output back to orchestrator
- owns its own filesystem and pi state

Tech:
- Node.js
- `@mariozechner/pi-coding-agent`
- `ws`

### 3. Browser UI

Location:
- `apps/orchestrator/public/`

Responsibilities:
- create new instances
- send prompts to specific instances
- fork an instance
- merge one instance into another
- stop instances
- display terminal-like output
- display lineage info per instance

Frontend split into reusable pieces:
- `index.html` — shell + templates
- `styles.css` — styling
- `app.js` — app boot and event routing
- `cards.js` — instance card UI logic
- `socket.js` — websocket setup
- `dom.js` — tiny DOM helpers
- `lineage.js` — lineage state tracking for cards

---

## Why pi

We chose pi because it gives us:

- a real coding agent with tools
- RPC mode for embedding
- session persistence
- tool-capable interaction loop
- extensibility via SDK and extensions

We are currently using:
- `pi --mode rpc`

That means:
- the worker can run pi headlessly
- the orchestrator can treat it like a controlled agent process
- the frontend can stay browser-native instead of streaming a terminal PTY

---

## Why Docker container per instance

We initially prototyped multiple pi processes in one container, but moved to:

**one container per agent instance**

Benefits:
- stronger isolation
- easier resource control
- clearer lineage semantics
- better mental model for fork/merge
- future compatibility with snapshotting and branch trees

Each worker container contains:
- the app workspace at `/workspace`
- pi state at `/state/pi-agent`
- metadata at `/state/meta`

Important environment variables:
- `PI_WORKSPACE=/workspace`
- `PI_CODING_AGENT_DIR=/state/pi-agent`
- `PI_AGENT_UUID=<unique id>`

---

## Current state layout inside each worker

### `/workspace`
Contains the git working tree / project files the agent edits.

### `/state/pi-agent`
Contains pi session and agent state.

### `/state/meta`
Contains orchestrator-written metadata such as:
- merge context
- merge details
- later: richer lineage and checkpoint metadata

This structure is important because we want:
- filesystem lineage
- session/context lineage
- future merge reasoning

---

## Current model defaults

We switched the default model to:
- `openai/gpt-5.4-mini`

Configured in:
- `apps/orchestrator/.env`
- `apps/orchestrator/.env.example`

This was done because earlier prompts with `gpt-4o-mini` tended to explain or plan instead of actually modifying files.

---

## Fork implementation

### User-level concept
Fork means:
- create a new child instance from a parent’s current state

### Current implementation
1. source worker is snapshotted with `docker commit`
2. a new worker container is launched from that snapshot image
3. the child gets a new `PI_AGENT_UUID`
4. UI lineage marks the new instance as a child of the source

This gives us filesystem-level branching through Docker layers without bind-mounted workspace copying.

### Why this matters
We want Level 2 semantics:
- preserve filesystem state
- preserve pi state
- do not attempt to snapshot live process RAM

This is the right tradeoff for a hackathon prototype and likely for the product too.

---

## Merge implementation

We explicitly chose:

**Git-native merge transport instead of raw filesystem copying**

### Why
It is cleaner for:
- branch semantics
- provenance
- future selective merges
- debugging and reproducibility

### Current merge flow
1. source instance checkpoints if dirty
2. target instance is first snapshotted and forked into a fresh **integration instance**
3. source exports a Git bundle with:
   - `git bundle create ... --all`
4. orchestrator reads the bundle from the source container
5. orchestrator injects the bundle into the integration container
6. integration instance adds the bundle as a remote-like source and fetches it
7. integration instance runs a real `git merge`
8. orchestrator reads session data from both original branches
9. orchestrator asks OpenAI to write a merged context summary
10. summary is written to the integration instance at:
   - `/state/meta/merge-context.md`
   - `/state/meta/merge-details.json`

### Current behavior
This already produces:
- successful merges when branches are non-overlapping
- real merge conflicts when they overlap
- non-destructive integration branches because the original target branch is preserved

That is a good sign: the merge primitive is real, not simulated.

---

## Lineage model: current and next step

### What we have now in the UI
Per instance card we show:
- root
- parent
- merged-from list

This is currently frontend-tracked lineage.

### What we still need
A stronger lineage model should track:
- instance ID (`piagent_uuid`)
- snapshot IDs
- parent instance
- root ancestor
- merge history
- current git commit
- latest pi session path
- checkpoint history

The next real upgrade should be to make lineage first-class in backend state and `/state/meta/lineage.json`.

---

## End-to-end results we verified

We actually ran the system on the VM after installing Docker.

### What we tested
- created initial instance
- had it write/modify code in the filesystem
- forked from it
- diverged two branches
- merged them back

### Outcomes observed
- forking works
- merge transport works
- clean merges can happen
- conflicting merges can happen
- conflict details are surfaced back through the orchestrator
- merge context files are written into worker state

One concrete result:
- a real merge conflict occurred when both branches created overlapping Tic Tac Toe files
- this is expected and proves the merge is real

---

## Why this is interesting beyond a demo

The important leap is:

We are not just spinning up chatbots.
We are making **agent work branchable and mergeable like software**.

This suggests a future where:
- you fork an agent into multiple directions
- let each branch solve a variation of the task
- compare diffs and context summaries
- merge the best branch back
- keep full ancestry and rationale

It’s basically:
- Git for code
- plus branch-aware agent context
- plus AI-assisted reconciliation

---

## Product vision

### Short version
A multi-agent coding environment where every agent branch is a first-class software branch.

### Longer version
Users can:
- create an instance from a base repo
- ask it to implement a feature
- fork at stable checkpoints
- let sibling branches try different approaches
- merge successful ideas back together
- later resolve merge conflicts with AI assistance
- later merge both code and session context in a principled way

This is useful because coding work is exploratory. Agent work should be exploratory too.

---

## Important design principles we discovered

### 1. Stable fork points matter
Forking arbitrary in-flight state is messy.
We want checkpoint-based forks.

### 2. Filesystem lineage and context lineage are separate
Code branches and conversation branches are related, but not identical.
We need both.

### 3. Git-native merge beats raw file copying
Git gives us much better branch semantics and auditability.

### 4. Container-per-instance is the right isolation boundary
It makes lineage and orchestration much cleaner.

### 5. UI must show structure, not just output
Users need to see ancestry, merge targets, and branch state, not just terminals.

---

## Suggested next technical steps

### Short-term
- make agents default to implementation rather than explanation
- add filesystem-changed / tools-used indicators to the UI
- make lineage backend-native, not just UI-native
- write `/state/meta/lineage.json`
- checkpoint automatically when the agent becomes idle

### Medium-term
- real checkpoint objects: git SHA + docker snapshot + session file
- fork only from checkpoints
- queue or resolve mid-run fork requests to latest checkpoint
- add AI-assisted conflict resolution after merge conflicts
- add richer branch graph UI

### Longer-term
- merge code and context together as a first-class operation
- let users compare multiple branches side by side
- add branch tree / timeline views
- support selective commit import / cherry-pick flows
- benchmark model behavior for code-first execution

---

## Slide deck breakdown

## Slide 1 — Title
**Agentsofchaos**
Forkable and mergeable coding agents in the browser.

Talking points:
- each agent runs in its own container
- branches are real
- merges are real
- code and context both matter

## Slide 2 — Problem
Current coding agents are linear.

Talking points:
- one prompt history
- one evolving state
- hard to explore alternatives cleanly
- hard to compare strategies
- no natural equivalent of branching and merging

## Slide 3 — Core idea
Treat agent work like software branches.

Talking points:
- create instance
- fork into variants
- let branches diverge
- merge good ideas back
- preserve ancestry

## Slide 4 — Architecture
Browser → Orchestrator → Docker workers → pi RPC

Talking points:
- Node orchestrator
- one worker container per pi instance
- pi RPC inside each worker
- Git + Docker snapshots as branch substrate

## Slide 5 — Fork and merge mechanics
Fork via Docker snapshot.
Merge via Git bundle + `git merge`.

Talking points:
- cheap-ish branching through Docker layers
- Git-native transfer instead of raw file copying
- real merge success/failure semantics

## Slide 6 — State model
Per worker:
- `/workspace`
- `/state/pi-agent`
- `/state/meta`

Talking points:
- code state
- session state
- metadata / merge context

## Slide 7 — What we demonstrated
Real E2E branch/merge flow.

Talking points:
- create instance
- implement feature
- fork
- diverge branches
- merge back
- observed real merge conflicts

## Slide 8 — Why this matters
This changes the unit of agent work.

Talking points:
- not just one assistant
- a graph of alternatives
- explore safely
- compare ideas
- recover and merge deliberately

## Slide 9 — Future direction
Checkpoint-based branching + AI-assisted merges.

Talking points:
- checkpoint every idle point
- fork from checkpoints only
- merge code and context
- resolve conflicts with AI
- richer lineage graph UI

## Slide 10 — Closing
**Agents should branch and merge like code.**

Talking points:
- software is exploratory
- agent work should be too
- branching is the missing primitive

---

## Demo script idea
1. Create first instance
2. Ask it to implement a simple feature
3. Fork it
4. Let root and child take different directions
5. Merge child back
6. Show either:
   - clean merge, or
   - real conflict + merge-context file
7. Show lineage on the cards

---

## Honest limitations to mention
- model behavior still sometimes explains instead of acting
- lineage is currently only partially formalized
- merge conflict resolution is not automated yet
- checkpointing should become first-class
- UI is still prototype-grade

Those are good hackathon caveats and also good next milestones.

---

## Immediate priorities while full design context is still fresh

These are the highest-value next steps to finish before losing chat context:

### 1. Checkpoint-first branching
Implement stable fork points explicitly.

Desired behavior:
- when an agent finishes and becomes idle, create a checkpoint
- checkpoint should include:
  - git commit SHA
  - Docker snapshot/image tag
  - latest pi session path
  - timestamp
- forks should default to the latest completed checkpoint
- mid-run fork requests should resolve to the last checkpoint, not live mutable state

Why this matters:
- makes branching deterministic
- simplifies lineage
- avoids forking half-finished tool runs

### 2. Backend-native lineage
Lineage is currently mostly UI-side.

Need to make lineage first-class in backend and worker metadata:
- `instanceId`
- `parentInstanceId`
- `rootInstanceId`
- `snapshotId`
- `mergedFrom`
- current git commit
- latest pi session path

Persist into:
- `/state/meta/lineage.json`

Why this matters:
- UI can always reconstruct ancestry
- merge history becomes durable
- later branch trees become straightforward

### 3. Integration-instance merge flow + resolver instance
We already switched merge semantics toward:
- fork target A into integration instance M
- merge B into M

Next step:
- on merge conflict, spawn a dedicated resolver instance from M
- let pi resolve conflicts there instead of stopping at raw conflict state

Why this matters:
- keeps A and B pristine
- makes merge resolution non-destructive
- is the cleanest branch semantics

### 4. Context merge as a first-class pipeline
Current merge writes one merged context summary, but we need the actual structure formalized.

Target flow:
- summarize/compact branch A context
- summarize/compact branch B context
- hand both summaries to the integration or resolver instance
- let pi produce merged context and next-step prompt
- persist artifacts in `/state/meta/`

Suggested files:
- `source-summary.md`
- `target-summary.md`
- `merge-context.md`
- `merge-details.json`

Why this matters:
- code merge without context merge is incomplete
- this is a key differentiator of the project

### 5. Make agents code-first by default
We observed that some prompts still get explanation-only responses.

Need to change defaults so that when user says:
- "build X"
- "implement Y"

pi should:
- inspect files
- edit files
- commit checkpointed work
- only explain if blocked or explicitly asked

Possible implementation:
- stronger default system prompt
- or a pi extension injecting action-first instructions

Why this matters:
- makes the product feel like a coding system, not a consultant chat

### 6. Show filesystem action in UI
Add explicit indicators per instance:
- tools used in last run
- filesystem changed yes/no
- latest git commit SHA
- clean / dirty / conflicted state

Why this matters:
- helps users trust that work actually happened
- makes debugging model behavior much easier

### 7. Tighten the E2E scenarios
The E2E flow is real, but overlapping branches often touch the same generated files and conflict immediately.

We should create two categories of tests:
- clean merge scenario
- intentional conflict scenario

Why this matters:
- gives us a reliable demo path
- keeps conflict handling visible without blocking all demos

### 8. Prepare the hackathon demo flow
Polish the exact flow we want to show live:
1. create base instance
2. implement small feature
3. fork into two variants
4. make clearly different branch changes
5. integrate one branch cleanly
6. show conflict or resolver flow on the second
7. show lineage and merged context

Why this matters:
- this is the product story in one sequence

---

## Recommended execution order

If we continue coding after compaction, the best order is:

1. checkpoint-first branching
2. backend-native lineage
3. integration + resolver merge flow
4. structured context merge artifacts
5. code-first prompting behavior
6. UI trust signals
7. polished demo/E2E scripts

This order preserves the architectural intent and de-risks the branch/merge story first.
