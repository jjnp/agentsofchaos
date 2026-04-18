<script lang="ts">
	import AgentCanvas from '$lib/components/agent-graph/AgentCanvas.svelte';
	import { demoAgentNodePlacements, demoAgentNodes } from '$lib/agent-graph/fixtures';
	import type { AgentNodeId } from '$lib/agent-graph/types';

	const nodes = demoAgentNodes;
	const placements = demoAgentNodePlacements;
	let selectedNodeId = $state<AgentNodeId | null>(nodes[4]?.id ?? nodes[0]?.id ?? null);

	const selectedNode = $derived(nodes.find((node) => node.id === selectedNodeId) ?? null);
	const selectedPlacement = $derived(
		selectedNodeId
			? (placements.find((placement) => placement.nodeId === selectedNodeId) ?? null)
			: null
	);
	const parentNode = $derived(
		selectedNode?.parentId
			? (nodes.find((node) => node.id === selectedNode.parentId) ?? null)
			: null
	);
	const childCount = $derived(
		selectedNode ? nodes.filter((node) => node.parentId === selectedNode.id).length : 0
	);
</script>

<svelte:head>
	<title>Agents of Chaos</title>
	<meta name="description" content="Graph canvas foundation for agent nodes and connections." />
</svelte:head>

<div class="canvas-page">
	<section class="canvas-page__stage panel">
		<AgentCanvas bind:selectedNodeId {nodes} {placements} class="h-[78vh]" />
	</section>

	<aside class="canvas-page__inspector panel">
		<p class="canvas-page__eyebrow">Selected node</p>
		{#if selectedNode}
			<h1 class="canvas-page__title">{selectedNode.name}</h1>
			<dl class="canvas-page__details">
				<div>
					<dt>ID</dt>
					<dd>{selectedNode.id}</dd>
				</div>
				<div>
					<dt>Parent</dt>
					<dd>{parentNode?.name ?? 'None'}</dd>
				</div>
				<div>
					<dt>Children</dt>
					<dd>{childCount}</dd>
				</div>
				<div>
					<dt>Canvas position</dt>
					<dd>
						{selectedPlacement ? `${selectedPlacement.x}, ${selectedPlacement.y}` : 'Missing'}
					</dd>
				</div>
			</dl>
		{:else}
			<h1 class="canvas-page__title">No node selected</h1>
		{/if}
	</aside>
</div>
