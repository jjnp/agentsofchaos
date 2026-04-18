import { samplePiSummary } from '../pi-summary/sample-pi-summary';
import { sampleNodeDiff, sampleNodePrompt } from './sample-node-diff';

export const sampleGraphNodes = [
	{
		id: 'node-demo-1',
		title: 'Inspect diff summaries for one node',
		status: 'active',
		prompt: sampleNodePrompt,
		diff: sampleNodeDiff,
		context:
			'The user wants a graph-node diff detail view with overall summaries and lazy file-level summaries.',
		summary: samplePiSummary
	},
	{
		id: 'node-demo-2',
		title: 'Refine graph-side inspector affordances',
		status: 'branch',
		prompt: 'Refine the node detail panel so users can move between changed files more quickly.',
		diff: `diff --git a/src/lib/components/NodePanel.svelte b/src/lib/components/NodePanel.svelte
index 4444444..5555555 100644
--- a/src/lib/components/NodePanel.svelte
+++ b/src/lib/components/NodePanel.svelte
@@ -1,5 +1,11 @@
 <script lang="ts">
   export let node;
+  export let selectedFilePath = null;
 </script>
 
 <aside>
+  <header>
+    <h2>{node.title}</h2>
+    <p>{selectedFilePath ?? 'Select a file to inspect'}</p>
+  </header>
   <slot />
 </aside>
diff --git a/src/lib/state/selection.ts b/src/lib/state/selection.ts
new file mode 100644
index 0000000..6666666
--- /dev/null
+++ b/src/lib/state/selection.ts
@@ -0,0 +1,8 @@
+export function createSelectedFileState() {
+  let selectedFilePath = null;
+
+  return {
+    get: () => selectedFilePath,
+    set: (path) => (selectedFilePath = path)
+  };
+}
`,
		context:
			'This branch explores a more explicit relationship between a graph node detail panel and the selected changed file.',
		summary: `# Node Panel Exploration Summary

## User intent
The goal of this branch is to make the node detail panel feel more connected to the currently selected file inside a node review flow.

## What changed
- Added a selected file label to the node panel header.
- Added a tiny state helper to persist the currently selected file path.

## Progress steps
- [x] Exposed selected file state in the panel surface.
- [x] Added a lightweight state helper for file selection.
- [ ] Decide whether file selection should be global graph state or node-local state.

## UX implication
This should reduce context loss when users switch between files because the active file remains visible in the surrounding node UI.

## Suggested next step
Test whether the selected file should also influence graph-edge previews, merge preparation, and cross-node comparisons.`
	}
] as const;
