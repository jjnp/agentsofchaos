<script lang="ts">
	import { getAgentGraphContext } from '$lib/agent-graph/context';
	import type { AgentNode, AgentNodePlacement } from '$lib/agent-graph/types';

	let {
		node,
		placement
	}: {
		node: AgentNode;
		placement: AgentNodePlacement;
	} = $props();

	type LabelAnchor = 'start' | 'middle' | 'end';

	const graphState = getAgentGraphContext();

	const isSelected = $derived(graphState.selectedNodeId === node.id);
	const isRootNode = $derived(node.parentId === null);
	const isLeftSide = $derived(!isRootNode && placement.x < 0);
	const labelAnchor = $derived<LabelAnchor>(isRootNode ? 'middle' : isLeftSide ? 'end' : 'start');
	const labelOffsetX = $derived(isRootNode ? 0 : isLeftSide ? -18 : 18);
	const dotRadius = $derived(isRootNode ? 11 : 9);
	const ringRadius = $derived(isRootNode ? 18 : 15);
	const showNodeDetails = $derived(graphState.isNodeDetailsVisible(node.id));
	const showDetails = $derived(node.details !== null && showNodeDetails);
	const showTitleLabel = $derived(!showNodeDetails);
	const detailBoxWidth = 152;
	const detailBoxHeight = 62;
	const detailBoxOffsetX = $derived(isRootNode ? 22 : isLeftSide ? -(detailBoxWidth + 26) : 26);
	const detailTextAnchor = $derived<LabelAnchor>(isLeftSide ? 'end' : 'start');
	const detailTextX = $derived(
		isLeftSide ? detailBoxOffsetX + detailBoxWidth - 12 : detailBoxOffsetX + 12
	);
	const contextUsageText = $derived(
		node.details ? `Context ${node.details.contextUsage.percentage}%` : ''
	);

	const handleSelect = () => {
		graphState.setSelectedNodeId(node.id);
	};
</script>

<g
	class:selected={isSelected}
	class:root={isRootNode}
	class="agent-node"
	transform={`translate(${placement.x} ${placement.y})`}
	tabindex="0"
	role="button"
	aria-label={node.name}
	data-agent-node-interactive="true"
	onclick={handleSelect}
	onmousedown={(event) => {
		event.preventDefault();
	}}
	onkeydown={(event) => {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			handleSelect();
		}
	}}
>
	{#if showDetails}
		<g class="agent-node__details">
			<rect
				x={detailBoxOffsetX}
				y={-detailBoxHeight / 2}
				width={detailBoxWidth}
				height={detailBoxHeight}
				rx="14"
				class="agent-node__details-panel"
			></rect>
			<text x={detailTextX} y="-10" text-anchor={detailTextAnchor} class="agent-node__details-name">
				{node.name}
			</text>
			<text
				x={detailTextX}
				y="10"
				text-anchor={detailTextAnchor}
				class="agent-node__details-context"
			>
				{contextUsageText}
			</text>
		</g>
	{/if}

	<circle class="agent-node__selection-ring" r={ringRadius}></circle>
	<circle class="agent-node__hit" r={ringRadius + 8}></circle>
	<circle class="agent-node__dot" r={dotRadius}></circle>
	{#if showTitleLabel}
		<text
			class="agent-node__label"
			x={labelOffsetX}
			y={isRootNode ? -22 : 3}
			text-anchor={labelAnchor}
		>
			{node.name}
		</text>
	{/if}
</g>

<style>
	.agent-node {
		cursor: pointer;
		user-select: none;
		-webkit-user-select: none;
	}

	.agent-node:focus,
	.agent-node:focus-visible {
		outline: none;
	}

	.agent-node__selection-ring {
		fill: none;
		stroke: color-mix(in srgb, var(--color-primary) 68%, transparent);
		stroke-dasharray: 3 5;
		opacity: 0;
	}

	.agent-node.selected .agent-node__selection-ring,
	.agent-node:focus-visible .agent-node__selection-ring {
		opacity: 1;
	}

	.agent-node__hit {
		fill: transparent;
	}

	.agent-node__dot {
		fill: var(--color-canvas);
		stroke: color-mix(in srgb, var(--color-text) 48%, var(--color-border));
		stroke-width: 1.5;
		transition:
			stroke 180ms ease,
			fill 180ms ease,
			transform 180ms ease;
	}

	.agent-node.root .agent-node__dot,
	.agent-node:hover .agent-node__dot,
	.agent-node.selected .agent-node__dot,
	.agent-node:focus-visible .agent-node__dot {
		stroke: var(--color-primary);
	}

	.agent-node.selected .agent-node__dot,
	.agent-node:focus-visible .agent-node__dot {
		fill: var(--color-primary);
	}

	.agent-node.root .agent-node__dot {
		fill: color-mix(in srgb, var(--color-primary) 10%, var(--color-canvas));
	}

	.agent-node.selected.root .agent-node__dot,
	.agent-node.root:focus-visible .agent-node__dot {
		fill: var(--color-primary);
	}

	.agent-node__label,
	.agent-node__details-name,
	.agent-node__details-context {
		font-family: var(--font-sans);
	}

	.agent-node__label {
		fill: var(--color-text);
		font-size: 0.84rem;
		cursor: pointer;
		user-select: none;
		-webkit-user-select: none;
	}

	.agent-node__details-panel {
		fill: rgb(18 19 15 / 0.88);
		stroke: color-mix(in srgb, var(--color-border) 72%, var(--color-primary) 18%);
		stroke-width: 1;
	}

	.agent-node__details-name {
		fill: var(--color-text);
		font-size: 0.72rem;
		font-weight: 600;
	}

	.agent-node__details-context {
		fill: color-mix(in srgb, var(--color-primary) 54%, var(--color-text));
		font-size: 0.68rem;
	}
</style>
