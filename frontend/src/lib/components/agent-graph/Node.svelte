<script lang="ts">
	import type { Node, NodeId } from '$lib/orchestrator/contracts';

	import { structuralParentId } from '$lib/agent-graph/types';

	interface Props {
		node: Node;
		x: number;
		y: number;
		isSelected: boolean;
		isMergeTarget?: boolean;
		isMergeSource?: boolean;
		onSelect: (id: NodeId) => void;
		onPointerDown?: (id: NodeId, event: PointerEvent) => void;
	}

	let {
		node,
		x,
		y,
		isSelected,
		isMergeTarget = false,
		isMergeSource = false,
		onSelect,
		onPointerDown
	}: Props = $props();

	type LabelAnchor = 'start' | 'middle' | 'end';

	const isRoot = $derived(structuralParentId(node) === null);
	const isRunning = $derived(node.status === 'running');
	const isLeftSide = $derived(!isRoot && x < 0);
	const labelAnchor = $derived<LabelAnchor>(isRoot ? 'middle' : isLeftSide ? 'end' : 'start');
	const labelOffsetX = $derived(isRoot ? 0 : isLeftSide ? -24 : 24);
	const dotRadius = $derived(isRoot ? 16.5 : 13.5);
	const ringRadius = $derived(isRoot ? 27 : 22.5);
	const spinnerRadius = $derived(isRoot ? 6.2 : 5.2);
</script>

<g
	class="agent-node"
	class:selected={isSelected}
	class:merge-target={isMergeTarget}
	class:merge-source={isMergeSource}
	class:root={isRoot}
	class:status-failed={node.status === 'failed'}
	class:status-cancelled={node.status === 'cancelled'}
	class:status-code-conflicted={node.status === 'code_conflicted'}
	class:status-context-conflicted={node.status === 'context_conflicted'}
	class:status-both-conflicted={node.status === 'both_conflicted'}
	class:kind-merge={node.kind === 'merge'}
	transform="translate({x} {y})"
	tabindex="0"
	role="button"
	aria-label="{node.title} ({node.kind} · {node.status})"
	data-agent-node-interactive="true"
	data-agent-node-id={node.id}
	onclick={() => onSelect(node.id)}
	onmousedown={(event) => event.preventDefault()}
	onpointerdown={(event) => {
		event.stopPropagation();
		onPointerDown?.(node.id, event);
	}}
	onkeydown={(event) => {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			onSelect(node.id);
		}
	}}
>
	<circle class="agent-node__selection-ring" r={ringRadius}></circle>
	<circle class="agent-node__hit" r={ringRadius + 8}></circle>
	<circle class="agent-node__dot" r={dotRadius}></circle>
	{#if isRunning}
		<g aria-hidden="true">
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
	<text
		class="agent-node__label"
		x={labelOffsetX}
		y={isRoot ? -22 : 3}
		text-anchor={labelAnchor}
	>
		{node.title.length > 36 ? `${node.title.slice(0, 35)}…` : node.title}
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
	.agent-node.merge-target .agent-node__selection-ring,
	.agent-node.merge-source .agent-node__selection-ring,
	.agent-node:focus-visible .agent-node__selection-ring {
		opacity: 1;
	}

	.agent-node.merge-target .agent-node__selection-ring {
		stroke: color-mix(in srgb, var(--color-primary-accent) 78%, transparent);
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
			fill 180ms ease;
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

	.agent-node.kind-merge .agent-node__dot {
		stroke: var(--color-kind-merge);
	}

	.agent-node.status-failed .agent-node__dot,
	.agent-node.status-both-conflicted .agent-node__dot {
		stroke: var(--color-danger);
	}
	.agent-node.status-cancelled .agent-node__dot {
		stroke: var(--color-text-muted);
	}
	.agent-node.status-code-conflicted .agent-node__dot {
		stroke: var(--color-status-code-conflicted);
	}
	.agent-node.status-context-conflicted .agent-node__dot {
		stroke: var(--color-status-context-conflicted);
	}

	.agent-node__spinner {
		pointer-events: none;
	}
	.agent-node__spinner-track,
	.agent-node__spinner-arc {
		fill: none;
		stroke: var(--node-spinner-color, var(--color-primary-accent));
		stroke-width: 1.6;
		stroke-linecap: round;
	}
	.agent-node__spinner-track {
		opacity: 0.22;
	}
	.agent-node__spinner-arc {
		stroke-dasharray: 34 66;
		filter: drop-shadow(0 0 0.35rem color-mix(in srgb, var(--color-primary-accent) 34%, transparent));
	}
	.agent-node__spinner-head {
		fill: var(--node-spinner-color, var(--color-primary-accent));
		filter: drop-shadow(0 0 0.35rem color-mix(in srgb, var(--color-primary-accent) 34%, transparent));
	}
	.agent-node.selected,
	.agent-node:focus-visible {
		--node-spinner-color: var(--color-canvas);
	}

	.agent-node__label {
		fill: var(--color-text);
		font-size: 0.84rem;
		cursor: pointer;
		user-select: none;
		-webkit-user-select: none;
		font-family: var(--font-sans);
	}
</style>
