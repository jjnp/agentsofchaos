export const sampleNodePrompt =
	'Add a dedicated node diff inspector with summaries and lazy per-file analysis.';

export const sampleNodeDiff = `diff --git a/src/lib/components/Graph.svelte b/src/lib/components/Graph.svelte
index 1111111..2222222 100644
--- a/src/lib/components/Graph.svelte
+++ b/src/lib/components/Graph.svelte
@@ -8,6 +8,10 @@
 export let nodes = [];
 export let edges = [];
 
+function openNodeDetails(nodeId: string) {
+  dispatch('inspect-node', { nodeId });
+}
+
 function focusNode(nodeId: string) {
   activeNodeId = nodeId;
 }
diff --git a/src/lib/server/graph-summary.ts b/src/lib/server/graph-summary.ts
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/src/lib/server/graph-summary.ts
@@ -0,0 +1,7 @@
+export function summarizeNode(node) {
+  return {
+    title: node.title,
+    changedFiles: node.changedFiles.length,
+    prompt: node.prompt
+  };
+}
`;
