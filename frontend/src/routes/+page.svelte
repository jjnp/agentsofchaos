<script lang="ts">
	import { computeLayoutPlacements, getPlacementLookup } from '$lib/agent-graph/layout';
	import { demoAgentNodePlacements, demoAgentNodes } from '$lib/agent-graph/fixtures';
	import AgentCanvas from '$lib/components/agent-graph/AgentCanvas.svelte';
	import Dropdown from '$lib/components/primitives/Dropdown.svelte';
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

	const activePlacements = $derived(
		computeLayoutPlacements({
			nodes,
			basePlacements,
			mode: activeLayoutMode
		})
	);
	const activePlacementLookup = $derived(getPlacementLookup(activePlacements));
	const selectedNode = $derived(nodes.find((node) => node.id === selectedNodeId) ?? null);
	const selectedPlacement = $derived(
		selectedNodeId ? (activePlacementLookup.get(selectedNodeId) ?? null) : null
	);
	const parentNode = $derived(
		selectedNode?.parentId
			? (nodes.find((node) => node.id === selectedNode.parentId) ?? null)
			: null
	);
	const childCount = $derived(
		selectedNode ? nodes.filter((node) => node.parentId === selectedNode.id).length : 0
	);

	const handleLayoutModeSelect = (option: ControlOption) => {
		activeLayoutMode = option.value as LayoutMode;
	};
</script>

<svelte:head>
	<title>Agents of Chaos</title>
	<meta name="description" content="Graph canvas foundation for agent nodes and connections." />
</svelte:head>

<div class="canvas-page">
	<section class="canvas-page__stage panel">
		<AgentCanvas
			bind:selectedNodeId
			bind:activeLayoutMode
			{nodes}
			placements={activePlacements}
			class="h-[78vh]"
		/>
	</section>

	<aside class="canvas-page__inspector panel">
		<div class="canvas-page__section">
			<p class="canvas-page__eyebrow">Layout</p>
			<Dropdown
				label="Layout mode"
				options={layoutModeOptions}
				value={activeLayoutMode}
				onSelect={handleLayoutModeSelect}
			/>
		</div>

		<div class="canvas-page__section">
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
							{selectedPlacement
								? `${Math.round(selectedPlacement.x)}, ${Math.round(selectedPlacement.y)}`
								: 'Missing'}
						</dd>
					</div>
				</dl>
			{:else}
				<h1 class="canvas-page__title">No node selected</h1>
			{/if}
		</div>
	</aside>
</div>
