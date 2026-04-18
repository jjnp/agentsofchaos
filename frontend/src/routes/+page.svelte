<script lang="ts">
	import { computeLayoutPlacements } from '$lib/agent-graph/layout';
	import { demoAgentNodePlacements, demoAgentNodes } from '$lib/agent-graph/fixtures';
	import AgentCanvas from '$lib/components/agent-graph/AgentCanvas.svelte';
	import AgentCanvasSidebar from '$lib/components/agent-graph/AgentCanvasSidebar.svelte';
	import type { ControlOption } from '$lib/components/primitives/types';
	import { layoutModes, type AgentNodeId, type LayoutMode } from '$lib/agent-graph/types';

	const nodes = demoAgentNodes;
	const basePlacements = demoAgentNodePlacements;

	const layoutModeOptions: readonly ControlOption[] = layoutModes.map((mode) => ({
		value: mode,
		label: mode === 'rings' ? 'Concentric rings' : mode === 'tree' ? 'Tree' : 'Force'
	}));

	let selectedNodeId = $state<AgentNodeId | null>(nodes[4]?.id ?? nodes[0]?.id ?? null);
	let activeLayoutMode = $state<LayoutMode>('rings');
	let isSidebarOpen = $state(true);

	const activePlacements = $derived(
		computeLayoutPlacements({
			nodes,
			basePlacements,
			mode: activeLayoutMode
		})
	);
</script>

<svelte:head>
	<title>Agents of Chaos</title>
	<meta name="description" content="Graph canvas foundation for agent nodes and connections." />
</svelte:head>

<div class="canvas-page">
	<AgentCanvas
		bind:selectedNodeId
		bind:activeLayoutMode
		{nodes}
		placements={activePlacements}
		class="h-screen rounded-none border-0"
	/>

	<AgentCanvasSidebar bind:activeLayoutMode bind:isOpen={isSidebarOpen} {layoutModeOptions} />
</div>
