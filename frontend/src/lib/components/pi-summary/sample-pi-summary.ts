export const samplePiSummary = `# Node Review Summary

## User intent
The user wanted a node-focused view that shows exactly what changed in one graph node, including diff inspection, summaries, and lazy per-file explanations.

## What was implemented
- Added a modular Svelte diff viewer for a single node.
- Added SvelteKit API endpoints for node overviews and per-file summaries.
- Combined prompt, diff, and compact context when generating summaries.
- Added source badges so the UI shows whether a summary came from AI or fallback logic.
- Added in-memory caching for repeated summary requests.

## Progress steps
- [x] Built a reusable node diff viewer component.
- [x] Added lazy loading for per-file summaries.
- [x] Implemented OpenAI-backed summary generation with fallback behavior.
- [x] Added caching and surfaced cached state in the UI.
- [ ] Wire the node inspector to real graph-node metadata from an API endpoint.

## Why this matters
The graph UI becomes easier to navigate because users can review a node as a compact decision artifact instead of reading a long terminal transcript or raw unified diff first.

## Open questions
- How much node metadata should be shown above the summary versus inside collapsible sections?
- Should progress steps reflect only completed work, or also planned next actions from the branch?
- Do we want file summaries to prefetch for the selected file only, or also for nearby files in the graph?

## Suggested next step
Connect this summary panel to real node metadata and persisted Pi outputs so the summary, progress steps, and diff all describe the same graph node state.`;
