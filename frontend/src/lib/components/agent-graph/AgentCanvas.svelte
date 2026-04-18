<script lang="ts">
	import { setAgentGraphContext } from '$lib/agent-graph/context';
	import {
		getCanvasPointFromScreen,
		getMaxNodeDepth,
		getRingRadiusForDepth,
		getCanvasTransform,
		getConnectionPath,
		getConnectionSegments,
		getMergePreviewPath,
		getMergedConnectionSegments,
		getStraightConnectionPath,
		getViewportAfterZoom,
		type CanvasPoint,
		type CanvasViewport
	} from '$lib/agent-graph/layout';
	import type { AgentGraphState } from '$lib/agent-graph/state.svelte';
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
		selectedNodeId: initialSelectedNodeId = null,
		activeLayoutMode = $bindable<LayoutMode>('rings'),
		showNodeDetailsForAll = true,
		onSelectedNodeChange,
		onMerge,
		minScale = 0.5,
		maxScale = 2.2,
		class: className = ''
	}: {
		nodes: readonly AgentNode[];
		placements: readonly AgentNodePlacement[];
		selectedNodeId?: AgentNodeId | null;
		activeLayoutMode?: LayoutMode;
		showNodeDetailsForAll?: boolean;
		onSelectedNodeChange?: (nodeId: AgentNodeId | null) => void;
		onMerge?: (sourceNodeId: AgentNodeId, targetNodeId: AgentNodeId) => void;
		minScale?: number;
		maxScale?: number;
		class?: string;
	} = $props();

	let internalSelectedNodeId = $state<AgentNodeId | null>(null);
	let visibleNodeDetailsIds = $state<readonly AgentNodeId[]>([]);
	let canvasElement = $state<HTMLDivElement | null>(null);
	let canvasWidth = $state(0);
	let canvasHeight = $state(0);
	let isPanning = $state(false);
	let activePointerId = $state<number | null>(null);
	let panStart = $state({ x: 0, y: 0 });
	let viewportStart = $state({ x: 0, y: 0 });
	let viewport = $state<CanvasViewport>({ x: 0, y: 0, scale: 1 });
	let mergeSourceNodeId = $state<AgentNodeId | null>(null);
	let mergeHoverNodeId = $state<AgentNodeId | null>(null);
	let mergePointerId = $state<number | null>(null);
	let mergePointerWorld = $state<CanvasPoint | null>(null);

	const graphState: AgentGraphState = {
		get nodes() {
			return nodes;
		},
		setNodes() {},
		get placements() {
			return placements;
		},
		setPlacements() {},
		get activeLayoutMode() {
			return activeLayoutMode;
		},
		setActiveLayoutMode(nextLayoutMode) {
			activeLayoutMode = nextLayoutMode;
		},
		get selectedNodeId() {
			return internalSelectedNodeId;
		},
		setSelectedNodeId(nextSelectedNodeId) {
			internalSelectedNodeId = nextSelectedNodeId;
		},
		isNodeDetailsVisible(nodeId) {
			return visibleNodeDetailsIds.includes(nodeId);
		},
		toggleNodeDetails(nodeId) {
			visibleNodeDetailsIds = visibleNodeDetailsIds.includes(nodeId)
				? visibleNodeDetailsIds.filter((visibleNodeId) => visibleNodeId !== nodeId)
				: [...visibleNodeDetailsIds, nodeId];
		},
		setAllNodeDetailsVisibility(isVisible) {
			visibleNodeDetailsIds = isVisible ? nodes.map((node) => node.id) : [];
		},
		get showNodeDetailsForAll() {
			return nodes.length > 0 && nodes.every((node) => visibleNodeDetailsIds.includes(node.id));
		}
	};

	setAgentGraphContext(() => graphState);

	$effect(() => {
		internalSelectedNodeId =
			initialSelectedNodeId && nodes.some((node) => node.id === initialSelectedNodeId)
				? initialSelectedNodeId
				: nodes.some((node) => node.id === internalSelectedNodeId)
					? internalSelectedNodeId
					: (nodes[0]?.id ?? null);
	});

	$effect(() => {
		visibleNodeDetailsIds = showNodeDetailsForAll ? nodes.map((node) => node.id) : [];
	});

	$effect(() => {
		onSelectedNodeChange?.(internalSelectedNodeId);
	});

	const placementLookup = $derived(
		new Map(placements.map((placement) => [placement.nodeId, placement]))
	);
	const connectionSegments = $derived(getConnectionSegments(nodes, placements));
	const mergedConnectionSegments = $derived(getMergedConnectionSegments(nodes, placements));
	const mergeSourcePlacement = $derived(
		mergeSourceNodeId ? (placementLookup.get(mergeSourceNodeId) ?? null) : null
	);
	const mergeTargetPlacement = $derived(
		mergeHoverNodeId ? (placementLookup.get(mergeHoverNodeId) ?? null) : null
	);
	const mergePreviewEnd = $derived(
		mergeTargetPlacement
			? ({ x: mergeTargetPlacement.x, y: mergeTargetPlacement.y } satisfies CanvasPoint)
			: mergePointerWorld
	);
	const mergePreviewPath = $derived(
		mergeSourcePlacement && mergePreviewEnd
			? getMergePreviewPath(
					{ x: mergeSourcePlacement.x, y: mergeSourcePlacement.y },
					mergePreviewEnd
				)
			: null
	);
	const maxDepth = $derived(getMaxNodeDepth(nodes));
	const showDepthRings = $derived(activeLayoutMode === 'rings');
	const sceneTransform = $derived(
		getCanvasTransform(viewport, { width: canvasWidth, height: canvasHeight })
	);
	const patternTransform = $derived(
		`translate(${canvasWidth / 2 + viewport.x} ${canvasHeight / 2 + viewport.y}) scale(${viewport.scale})`
	);

	const getWorldPointForEvent = (event: PointerEvent) => {
		const rect = canvasElement?.getBoundingClientRect();
		if (!rect) {
			return null;
		}

		return getCanvasPointFromScreen({
			pointer: {
				x: event.clientX - rect.left,
				y: event.clientY - rect.top
			},
			viewport,
			canvasSize: { width: canvasWidth, height: canvasHeight }
		});
	};

	const clearMergeDrag = () => {
		if (
			canvasElement &&
			mergePointerId !== null &&
			canvasElement.hasPointerCapture(mergePointerId)
		) {
			canvasElement.releasePointerCapture(mergePointerId);
		}

		mergeSourceNodeId = null;
		mergeHoverNodeId = null;
		mergePointerId = null;
		mergePointerWorld = null;
	};

	const updateMergeHoverNode = (target: Element | null) => {
		if (!(target instanceof Element)) {
			mergeHoverNodeId = null;
			return;
		}

		const hoveredNodeId = target
			.closest<SVGGElement>('[data-agent-node-id]')
			?.getAttribute('data-agent-node-id');

		mergeHoverNodeId =
			hoveredNodeId && hoveredNodeId !== mergeSourceNodeId ? (hoveredNodeId as AgentNodeId) : null;
	};

	const handleNodePointerDown = (nodeId: AgentNodeId, event: PointerEvent) => {
		if (event.button !== 0) {
			return;
		}

		graphState.setSelectedNodeId(nodeId);
		mergeSourceNodeId = nodeId;
		mergeHoverNodeId = null;
		mergePointerId = event.pointerId;
		mergePointerWorld = getWorldPointForEvent(event);
		canvasElement?.setPointerCapture(event.pointerId);
	};

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
		if (mergeSourceNodeId && event.pointerId === mergePointerId) {
			mergePointerWorld = getWorldPointForEvent(event);
			updateMergeHoverNode(document.elementFromPoint(event.clientX, event.clientY));
			return;
		}

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

	const handlePointerUp = (event: PointerEvent) => {
		if (mergeSourceNodeId && event.pointerId === mergePointerId) {
			updateMergeHoverNode(document.elementFromPoint(event.clientX, event.clientY));
			if (mergeHoverNodeId) {
				onMerge?.(mergeSourceNodeId, mergeHoverNodeId);
			}
			clearMergeDrag();
			return;
		}

		stopPanning();
	};

	const handlePointerLeave = () => {
		if (!mergeSourceNodeId) {
			stopPanning();
		}
	};

	const handlePointerCancel = () => {
		clearMergeDrag();
		stopPanning();
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
	onpointerup={handlePointerUp}
	onpointerleave={handlePointerLeave}
	onpointercancel={handlePointerCancel}
	onwheel={handleWheel}
>
	<svg class="agent-canvas__scene" aria-label="Agent graph canvas">
		<defs>
			<marker
				id="agent-canvas-merged-arrow"
				viewBox="0 0 10 10"
				refX="10"
				refY="5"
				markerWidth="10"
				markerHeight="10"
				markerUnits="userSpaceOnUse"
				orient="auto-start-reverse"
			>
				<path d="M 0 0 L 10 5 L 0 10 z" class="agent-canvas__merged-arrowhead"></path>
			</marker>
			<marker
				id="agent-canvas-merge-arrow"
				viewBox="0 0 10 10"
				refX="10"
				refY="5"
				markerWidth="10"
				markerHeight="10"
				markerUnits="userSpaceOnUse"
				orient="auto-start-reverse"
			>
				<path d="M 0 0 L 10 5 L 0 10 z" class="agent-canvas__merge-arrowhead"></path>
			</marker>
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
				{#each mergedConnectionSegments as segment (`${segment.mergedNodeId}-${segment.targetNodeId}`)}
					<path
						d={getStraightConnectionPath(segment)}
						data-merged-source-node-id={segment.mergedNodeId}
						data-merged-target-node-id={segment.targetNodeId}
						class="agent-canvas__connection agent-canvas__connection--merged"
						marker-end="url(#agent-canvas-merged-arrow)"
					></path>
				{/each}
				{#if mergePreviewPath}
					<path
						d={mergePreviewPath}
						class="agent-canvas__merge-preview"
						marker-end="url(#agent-canvas-merge-arrow)"
					></path>
				{/if}
			</g>
			<g class="agent-canvas__nodes">
				{#each nodes as node (node.id)}
					{#if placementLookup.get(node.id)}
						<Node
							{node}
							placement={placementLookup.get(node.id)!}
							isMergeTarget={mergeHoverNodeId === node.id}
							isMergeSource={mergeSourceNodeId === node.id}
							onPointerDown={handleNodePointerDown}
						/>
					{/if}
				{/each}
			</g>
		</g>
	</svg>
</div>

<style>
	.agent-canvas {
		position: relative;
		width: 100%;
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
		stroke: color-mix(in srgb, var(--color-primary) 16%, rgb(255 255 255 / 0.12));
		stroke-dasharray: 4 8;
		vector-effect: non-scaling-stroke;
	}

	.agent-canvas__ring-label {
		fill: color-mix(in srgb, var(--color-text) 45%, var(--color-text-muted));
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

	.agent-canvas__connection--merged {
		stroke-dasharray: 6 6;
	}

	.agent-canvas__merged-arrowhead {
		fill: color-mix(in srgb, var(--color-primary) 34%, var(--color-text-muted));
	}

	.agent-canvas__merge-preview {
		fill: none;
		stroke: color-mix(in srgb, var(--color-primary-accent) 72%, var(--color-primary));
		stroke-width: 2;
		stroke-linecap: round;
		stroke-dasharray: 7 7;
		animation: agent-canvas-merge-dash 420ms linear infinite;
		vector-effect: non-scaling-stroke;
	}

	.agent-canvas__merge-arrowhead {
		fill: color-mix(in srgb, var(--color-primary-accent) 72%, var(--color-primary));
	}

	@keyframes agent-canvas-merge-dash {
		from {
			stroke-dashoffset: 0;
		}

		to {
			stroke-dashoffset: -14;
		}
	}
</style>
