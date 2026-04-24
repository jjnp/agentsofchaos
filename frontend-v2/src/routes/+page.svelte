<script lang="ts">
	import { onDestroy } from 'svelte';

	import { GraphStore } from '$lib/agent-graph/state.svelte';
	import AgentCanvas from '$lib/components/agent-graph/AgentCanvas.svelte';
	import CanvasControls from '$lib/components/canvas-controls/CanvasControls.svelte';
	import NodeSidebar from '$lib/components/node-view/NodeSidebar.svelte';
	import ProjectOpener from '$lib/components/project/ProjectOpener.svelte';

	const store = new GraphStore();

	onDestroy(() => store.dispose());
</script>

<svelte:head>
	<title>Agents of Chaos v2</title>
	<meta
		name="description"
		content="Graph-native UI for orchestrator-v2: immutable nodes, ephemeral runs, ancestor-based merges."
	/>
</svelte:head>

<div class="canvas-page">
	{#if !store.project}
		<div class="opener-overlay">
			<ProjectOpener {store} />
		</div>
	{:else}
		<NodeSidebar {store} />
		<AgentCanvas {store} />
		<CanvasControls {store} onCloseProject={() => store.closeProject()} />
	{/if}
</div>

<style>
	.canvas-page {
		position: relative;
		min-height: 100vh;
		overflow: hidden;
	}

	.opener-overlay {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.5rem;
	}

</style>
