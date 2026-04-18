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
	const labelAnchor = $derived<LabelAnchor>(
		isRootNode ? 'middle' : placement.x < 0 ? 'end' : 'start'
	);
	const labelOffsetX = $derived(isRootNode ? 0 : placement.x < 0 ? -18 : 18);
	const dotRadius = $derived(isRootNode ? 11 : 9);
	const ringRadius = $derived(isRootNode ? 18 : 15);

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
	<circle class="agent-node__selection-ring" r={ringRadius}></circle>
	<circle class="agent-node__hit" r={ringRadius + 8}></circle>
	<circle class="agent-node__dot" r={dotRadius}></circle>
	<text
		class="agent-node__label"
		x={labelOffsetX}
		y={isRootNode ? -22 : 3}
		text-anchor={labelAnchor}
	>
		{node.name}
	</text>
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

	.agent-node__label {
		font-family: var(--font-sans);
	}

	.agent-node__label {
		fill: var(--color-text);
		font-size: 0.84rem;
		cursor: pointer;
		user-select: none;
		-webkit-user-select: none;
	}
</style>
