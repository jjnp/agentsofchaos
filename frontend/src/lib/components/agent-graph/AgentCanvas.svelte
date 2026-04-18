<script lang="ts">
	import { setAgentGraphContext } from '$lib/agent-graph/context';
	import {
		getMaxNodeDepth,
		getRingRadiusForDepth,
		getCanvasTransform,
		getConnectionPath,
		getConnectionSegments,
		getViewportAfterZoom,
		type CanvasViewport
	} from '$lib/agent-graph/layout';
	import { createAgentGraphState } from '$lib/agent-graph/state.svelte';
	import type {
		AgentNode,
		AgentNodeId,
		AgentNodePlacement,
		LayoutMode
	} from '$lib/agent-graph/types';
	import Node from './Node.svelte';

	let {
		nodes,
		placements,
		selectedNodeId = $bindable<AgentNodeId | null>(null),
		activeLayoutMode = $bindable<LayoutMode>('rings'),
		minScale = 0.5,
		maxScale = 2.2,
		class: className = ''
	}: {
		nodes: readonly AgentNode[];
		placements: readonly AgentNodePlacement[];
		selectedNodeId?: AgentNodeId | null;
		activeLayoutMode?: LayoutMode;
		minScale?: number;
		maxScale?: number;
		class?: string;
	} = $props();

	const graphState = createAgentGraphState([], [], null, activeLayoutMode);
	setAgentGraphContext(() => graphState);

	let viewport = $state<CanvasViewport>({ x: 0, y: 0, scale: 1 });
	let canvasElement = $state<HTMLDivElement | null>(null);
	let canvasWidth = $state(0);
	let canvasHeight = $state(0);
	let isPanning = $state(false);
	let activePointerId = $state<number | null>(null);
	let panStart = $state({ x: 0, y: 0 });
	let viewportStart = $state({ x: 0, y: 0 });

	$effect(() => {
		graphState.setNodes(nodes);
		graphState.setPlacements(placements);
		if (!graphState.selectedNodeId && nodes[0]) {
			graphState.setSelectedNodeId(nodes[0].id);
		}
	});

	$effect(() => {
		graphState.setSelectedNodeId(
			selectedNodeId ?? graphState.selectedNodeId ?? nodes[0]?.id ?? null
		);
	});

	$effect(() => {
		graphState.setActiveLayoutMode(activeLayoutMode);
	});

	$effect(() => {
		selectedNodeId = graphState.selectedNodeId;
	});

	$effect(() => {
		activeLayoutMode = graphState.activeLayoutMode;
	});

	const placementLookup = $derived(
		new Map(graphState.placements.map((placement) => [placement.nodeId, placement]))
	);
	const connectionSegments = $derived(
		getConnectionSegments(graphState.nodes, graphState.placements)
	);
	const maxDepth = $derived(getMaxNodeDepth(graphState.nodes));
	const showDepthRings = $derived(graphState.activeLayoutMode === 'rings');
	const sceneTransform = $derived(
		getCanvasTransform(viewport, { width: canvasWidth, height: canvasHeight })
	);
	const patternTransform = $derived(
		`translate(${canvasWidth / 2 + viewport.x} ${canvasHeight / 2 + viewport.y}) scale(${viewport.scale})`
	);

	const handlePointerDown = (event: PointerEvent) => {
		if (event.button !== 0) {
			return;
		}

		const target = event.target;
		if (target instanceof Element && target.closest('[data-agent-node-interactive="true"]')) {
			return;
		}

		isPanning = true;
		activePointerId = event.pointerId;
		panStart = { x: event.clientX, y: event.clientY };
		viewportStart = { x: viewport.x, y: viewport.y };
		canvasElement?.setPointerCapture(event.pointerId);
	};

	const handlePointerMove = (event: PointerEvent) => {
		if (!isPanning || event.pointerId !== activePointerId) {
			return;
		}

		viewport = {
			...viewport,
			x: viewportStart.x + (event.clientX - panStart.x),
			y: viewportStart.y + (event.clientY - panStart.y)
		};
	};

	const stopPanning = () => {
		isPanning = false;
		activePointerId = null;
	};

	const handleWheel = (event: WheelEvent) => {
		event.preventDefault();

		const rect = canvasElement?.getBoundingClientRect();
		if (!rect) {
			return;
		}

		const pointer = {
			x: event.clientX - rect.left,
			y: event.clientY - rect.top
		};

		viewport = getViewportAfterZoom({
			viewport,
			deltaY: event.deltaY,
			pointer,
			canvasSize: { width: canvasWidth, height: canvasHeight },
			minScale,
			maxScale
		});
	};
</script>

<div
	bind:this={canvasElement}
	bind:clientWidth={canvasWidth}
	bind:clientHeight={canvasHeight}
	class={`agent-canvas ${className}`}
	role="application"
	aria-label="Zoomable agent canvas"
	onpointerdown={handlePointerDown}
	onpointermove={handlePointerMove}
	onpointerup={stopPanning}
	onpointerleave={stopPanning}
	onwheel={handleWheel}
>
	<svg class="agent-canvas__scene" aria-label="Agent graph canvas">
		<defs>
			<pattern
				id="agent-canvas-grid"
				width="48"
				height="48"
				patternUnits="userSpaceOnUse"
				{patternTransform}
			>
				<path d="M 48 0 L 0 0 0 48" class="agent-canvas__grid-path"></path>
			</pattern>
		</defs>

		<rect width="100%" height="100%" fill="url(#agent-canvas-grid)"></rect>
		<g class="agent-canvas__camera" transform={sceneTransform}>
			{#if showDepthRings}
				<g class="agent-canvas__rings">
					{#each Array.from({ length: maxDepth }, (_, index) => index + 1) as depth (depth)}
						<circle r={getRingRadiusForDepth(depth)}></circle>
						<text x={getRingRadiusForDepth(depth) + 12} y={-10} class="agent-canvas__ring-label">
							Depth {String(depth).padStart(2, '0')}
						</text>
					{/each}
				</g>
			{/if}
			<g class="agent-canvas__connections">
				{#each connectionSegments as segment (segment.childId)}
					<path
						d={getConnectionPath(segment)}
						data-connection-child-id={segment.childId}
						class="agent-canvas__connection"
					></path>
				{/each}
			</g>
			<g class="agent-canvas__nodes">
				{#each graphState.nodes as node (node.id)}
					{#if placementLookup.get(node.id)}
						<Node {node} placement={placementLookup.get(node.id)!} />
					{/if}
				{/each}
			</g>
		</g>
	</svg>
</div>

<style>
	.agent-canvas {
		position: relative;
		overflow: hidden;
		min-height: 32rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 1.5rem;
		background: linear-gradient(180deg, rgb(13 13 11 / 0.98), rgb(8 8 8 / 1));
		cursor: grab;
	}

	.agent-canvas:active {
		cursor: grabbing;
	}

	.agent-canvas__scene {
		width: 100%;
		height: 100%;
		display: block;
		shape-rendering: geometricPrecision;
		text-rendering: geometricPrecision;
	}

	.agent-canvas__grid-path {
		fill: none;
		stroke: rgb(255 255 255 / 0.04);
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}

	.agent-canvas__rings circle {
		fill: none;
		stroke: rgb(255 255 255 / 0.07);
		stroke-dasharray: 4 8;
		vector-effect: non-scaling-stroke;
	}

	.agent-canvas__ring-label {
		fill: var(--color-text-muted);
		font-size: 0.65rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		vector-effect: non-scaling-stroke;
		user-select: none;
	}

	.agent-canvas__connection {
		fill: none;
		stroke: color-mix(in srgb, var(--color-primary) 34%, var(--color-text-muted));
		stroke-width: 1.5;
		stroke-linecap: round;
		vector-effect: non-scaling-stroke;
	}
</style>
