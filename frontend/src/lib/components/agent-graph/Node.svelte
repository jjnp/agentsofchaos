<script lang="ts">
	import { getAgentGraphContext } from '$lib/agent-graph/context';
	import type { AgentNode, AgentNodeId, AgentNodePlacement } from '$lib/agent-graph/types';

	let {
		node,
		placement,
		isMergeTarget = false,
		isMergeSource = false,
		onPointerDown
	}: {
		node: AgentNode;
		placement: AgentNodePlacement;
		isMergeTarget?: boolean;
		isMergeSource?: boolean;
		onPointerDown?: (nodeId: AgentNodeId, event: PointerEvent) => void;
	} = $props();

	type LabelAnchor = 'start' | 'middle' | 'end';

	const graphState = getAgentGraphContext();

	const isSelected = $derived(graphState.selectedNodeId === node.id);
	const isRootNode = $derived(node.parentId === null);
	const isRunning = $derived(node.status === 'running');
	const isLeftSide = $derived(!isRootNode && placement.x < 0);
	const labelAnchor = $derived<LabelAnchor>(isRootNode ? 'middle' : isLeftSide ? 'end' : 'start');
	const labelOffsetX = $derived(isRootNode ? 0 : isLeftSide ? -24 : 24);
	const dotRadius = $derived(isRootNode ? 16.5 : 13.5);
	const ringRadius = $derived(isRootNode ? 27 : 22.5);
	const spinnerRadius = $derived(isRootNode ? 6 : 5);
	const spinnerOffsetX = $derived(isLeftSide ? dotRadius + 12 : -(dotRadius + 12));
	const spinnerOffsetY = -1;
	const showNodeDetails = $derived(graphState.isNodeDetailsVisible(node.id));
	const showDetails = $derived(node.details !== null && showNodeDetails);
	const showTitleLabel = $derived(!showNodeDetails);
	const detailBoxWidth = 152;
	const detailBoxHeight = 62;
	const detailBoxOffsetX = $derived(isRootNode ? 30 : isLeftSide ? -(detailBoxWidth + 34) : 34);
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
	class:merge-target={isMergeTarget}
	class:merge-source={isMergeSource}
	class:root={isRootNode}
	class="agent-node"
	transform={`translate(${placement.x} ${placement.y})`}
	tabindex="0"
	role="button"
	aria-label={node.name}
	data-agent-node-interactive="true"
	data-agent-node-id={node.id}
	onclick={handleSelect}
	onmousedown={(event) => {
		event.preventDefault();
	}}
	onpointerdown={(event) => {
		event.stopPropagation();
		onPointerDown?.(node.id, event);
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
	{#if isRunning}
		<g
			transform={`translate(${spinnerOffsetX} ${spinnerOffsetY})`}
			data-node-spinner-for={node.id}
			aria-hidden="true"
		>
			<g class="agent-node__spinner">
				<circle class="agent-node__spinner-track" r={spinnerRadius}></circle>
				<circle
					class="agent-node__spinner-arc"
					r={spinnerRadius}
					pathLength="100"
					transform="rotate(-90)"
				></circle>
				<circle class="agent-node__spinner-head" cx="0" cy={-spinnerRadius} r="1.25"></circle>
				<animateTransform
					attributeName="transform"
					type="rotate"
					from="0 0 0"
					to="360 0 0"
					dur="850ms"
					repeatCount="indefinite"
				/>
			</g>
		</g>
	{/if}
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
	.agent-node.merge-target .agent-node__selection-ring,
	.agent-node.merge-source .agent-node__selection-ring,
	.agent-node:focus-visible .agent-node__selection-ring {
		opacity: 1;
	}

	.agent-node.merge-target .agent-node__selection-ring {
		stroke: color-mix(in srgb, var(--color-primary-accent) 72%, transparent);
		stroke-dasharray: 5 4;
	}

	.agent-node.merge-source .agent-node__selection-ring {
		stroke-dasharray: 5 4;
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
	.agent-node.merge-target .agent-node__dot,
	.agent-node.merge-source .agent-node__dot,
	.agent-node.selected .agent-node__dot,
	.agent-node:focus-visible .agent-node__dot {
		stroke: var(--color-primary);
	}

	.agent-node.merge-target .agent-node__dot {
		stroke: var(--color-primary-accent);
		fill: color-mix(in srgb, var(--color-primary-accent) 18%, var(--color-canvas));
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

	.agent-node__spinner {
		pointer-events: none;
	}

	.agent-node__spinner-track,
	.agent-node__spinner-arc {
		fill: none;
		stroke: var(--color-primary-accent);
		stroke-width: 1.6;
		stroke-linecap: round;
	}

	.agent-node__spinner-track {
		opacity: 0.22;
	}

	.agent-node__spinner-arc {
		stroke-dasharray: 34 66;
		filter: drop-shadow(
			0 0 0.35rem color-mix(in srgb, var(--color-primary-accent) 34%, transparent)
		);
	}

	.agent-node__spinner-head {
		fill: var(--color-primary-accent);
		filter: drop-shadow(
			0 0 0.35rem color-mix(in srgb, var(--color-primary-accent) 34%, transparent)
		);
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
