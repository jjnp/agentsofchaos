<script lang="ts">
	import { onMount } from 'svelte';

	import {
		getCanvasPointFromScreen,
		getCanvasTransform,
		getConnectionPath,
		getMaxNodeDepth,
		getMergePreviewPath,
		getRingRadiusForDepth,
		getStraightConnectionPath,
		getViewportAfterZoom
	} from '$lib/agent-graph/layout';
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { CanvasPoint, CanvasViewport } from '$lib/agent-graph/types';
	import type { NodeId } from '$lib/orchestrator/contracts';

	import Node from './Node.svelte';
	import NodePromptPopover from './NodePromptPopover.svelte';

	const NODE_RADIUS_WORLD = 22.5;
	const POPOVER_OFFSET_X = 18;
	const POPOVER_OFFSET_Y = -36;

	interface Props {
		store: GraphStore;
		minScale?: number;
		maxScale?: number;
	}

	let { store, minScale = 0.5, maxScale = 2.2 }: Props = $props();

	let canvasElement = $state<HTMLDivElement | null>(null);
	let canvasWidth = $state(0);
	let canvasHeight = $state(0);

	let viewport = $state<CanvasViewport>({ x: 0, y: 0, scale: 1 });

	let isPanning = $state(false);
	let panPointerId = $state<number | null>(null);
	let panStart = $state<CanvasPoint>({ x: 0, y: 0 });
	let viewportStart = $state<CanvasPoint>({ x: 0, y: 0 });

	let mergeSourceId = $state<NodeId | null>(null);
	let mergeHoverId = $state<NodeId | null>(null);
	let mergePointerId = $state<number | null>(null);
	let mergePointerWorld = $state<CanvasPoint | null>(null);

	const placementById = $derived(new Map(store.placements.map((p) => [p.nodeId, p])));
	const maxDepth = $derived(getMaxNodeDepth(store.nodes));
	const showDepthRings = $derived(store.activeLayoutMode === 'rings');

	const selectedPlacement = $derived(
		store.selectedNodeId ? (placementById.get(store.selectedNodeId) ?? null) : null
	);
	const selectedScreenPos = $derived.by(() => {
		if (!selectedPlacement || canvasWidth <= 0 || canvasHeight <= 0) {
			return null;
		}
		const x =
			canvasWidth / 2 +
			viewport.x +
			selectedPlacement.x * viewport.scale +
			(NODE_RADIUS_WORLD * viewport.scale + POPOVER_OFFSET_X);
		const y =
			canvasHeight / 2 +
			viewport.y +
			selectedPlacement.y * viewport.scale +
			POPOVER_OFFSET_Y;
		return { x, y };
	});
	const selectedNodeForPopover = $derived(
		store.selectedNode && !mergeSourceId ? store.selectedNode : null
	);

	const sceneTransform = $derived(
		getCanvasTransform(viewport, { width: canvasWidth, height: canvasHeight })
	);
	const patternTransform = $derived(
		`translate(${canvasWidth / 2 + viewport.x} ${canvasHeight / 2 + viewport.y}) scale(${viewport.scale})`
	);

	const mergeSourcePlacement = $derived(
		mergeSourceId ? (placementById.get(mergeSourceId) ?? null) : null
	);
	const mergeTargetPlacement = $derived(
		mergeHoverId ? (placementById.get(mergeHoverId) ?? null) : null
	);
	const mergePreviewEnd = $derived<CanvasPoint | null>(
		mergeTargetPlacement
			? { x: mergeTargetPlacement.x, y: mergeTargetPlacement.y }
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

	function recenterViewport() {
		if (store.placements.length === 0 || canvasWidth <= 0 || canvasHeight <= 0) {
			viewport = { x: 0, y: 0, scale: 1 };
			return;
		}
		const { minX, maxX, minY, maxY } = store.bounds;
		const horizontalPadding = 240;
		const verticalPadding = 220;
		const worldWidth = Math.max(maxX - minX + horizontalPadding, 220);
		const worldHeight = Math.max(maxY - minY + verticalPadding, 220);
		const fitted = Math.min(canvasWidth / worldWidth, canvasHeight / worldHeight);
		const scale = Math.min(Math.max(fitted, minScale), Math.min(maxScale, 1.2));
		const centerX = (minX + maxX) / 2;
		const centerY = (minY + maxY) / 2;
		viewport = {
			scale,
			x: -centerX * scale,
			y: -centerY * scale
		};
	}

	let lastRecenterKey = $state(0);
	onMount(() => {
		lastRecenterKey = store.recenterKey;
		recenterViewport();
	});

	$effect(() => {
		if (store.recenterKey === lastRecenterKey) return;
		lastRecenterKey = store.recenterKey;
		recenterViewport();
	});

	// Auto-recenter when first nodes appear, otherwise let the user pan freely.
	let lastNodeCount = $state(0);
	$effect(() => {
		const count = store.nodes.length;
		if (lastNodeCount === 0 && count > 0) {
			recenterViewport();
		}
		lastNodeCount = count;
	});

	function getWorldPointForEvent(event: PointerEvent): CanvasPoint | null {
		const rect = canvasElement?.getBoundingClientRect();
		if (!rect) return null;
		return getCanvasPointFromScreen({
			pointer: { x: event.clientX - rect.left, y: event.clientY - rect.top },
			viewport,
			canvasSize: { width: canvasWidth, height: canvasHeight }
		});
	}

	function clearMergeDrag() {
		if (
			canvasElement &&
			mergePointerId !== null &&
			canvasElement.hasPointerCapture(mergePointerId)
		) {
			canvasElement.releasePointerCapture(mergePointerId);
		}
		mergeSourceId = null;
		mergeHoverId = null;
		mergePointerId = null;
		mergePointerWorld = null;
	}

	function updateMergeHover(target: Element | null) {
		if (!(target instanceof Element)) {
			mergeHoverId = null;
			return;
		}
		const hovered = target
			.closest<SVGGElement>('[data-agent-node-id]')
			?.getAttribute('data-agent-node-id');
		mergeHoverId =
			hovered && hovered !== mergeSourceId ? (hovered as NodeId) : null;
	}

	function handleNodePointerDown(nodeId: NodeId, event: PointerEvent) {
		if (event.button !== 0) return;
		store.select(nodeId);
		mergeSourceId = nodeId;
		mergeHoverId = null;
		mergePointerId = event.pointerId;
		mergePointerWorld = getWorldPointForEvent(event);
		canvasElement?.setPointerCapture(event.pointerId);
	}

	function handlePointerDown(event: PointerEvent) {
		if (event.button !== 0) return;
		const target = event.target;
		if (target instanceof Element && target.closest('[data-agent-node-interactive="true"]')) {
			return;
		}
		isPanning = true;
		panPointerId = event.pointerId;
		panStart = { x: event.clientX, y: event.clientY };
		viewportStart = { x: viewport.x, y: viewport.y };
		canvasElement?.setPointerCapture(event.pointerId);
	}

	function handlePointerMove(event: PointerEvent) {
		if (mergeSourceId && event.pointerId === mergePointerId) {
			mergePointerWorld = getWorldPointForEvent(event);
			updateMergeHover(document.elementFromPoint(event.clientX, event.clientY));
			return;
		}
		if (!isPanning || event.pointerId !== panPointerId) return;
		viewport = {
			...viewport,
			x: viewportStart.x + (event.clientX - panStart.x),
			y: viewportStart.y + (event.clientY - panStart.y)
		};
	}

	function stopPanning() {
		isPanning = false;
		panPointerId = null;
	}

	function handlePointerUp(event: PointerEvent) {
		if (mergeSourceId && event.pointerId === mergePointerId) {
			updateMergeHover(document.elementFromPoint(event.clientX, event.clientY));
			if (mergeHoverId && mergeSourceId !== mergeHoverId) {
				const source = mergeSourceId;
				const target = mergeHoverId;
				void store.mergeNodes(source, target).catch((err: unknown) => {
					store.lastError = err instanceof Error ? err.message : String(err);
				});
			}
			clearMergeDrag();
			return;
		}
		stopPanning();
	}

	function handlePointerLeave() {
		if (!mergeSourceId) {
			stopPanning();
		}
	}

	function handlePointerCancel() {
		clearMergeDrag();
		stopPanning();
	}

	function handleWheel(event: WheelEvent) {
		event.preventDefault();
		const rect = canvasElement?.getBoundingClientRect();
		if (!rect) return;
		viewport = getViewportAfterZoom({
			viewport,
			deltaY: event.deltaY,
			pointer: { x: event.clientX - rect.left, y: event.clientY - rect.top },
			canvasSize: { width: canvasWidth, height: canvasHeight },
			minScale,
			maxScale
		});
	}
</script>

<div
	bind:this={canvasElement}
	bind:clientWidth={canvasWidth}
	bind:clientHeight={canvasHeight}
	class="agent-canvas"
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
						<text
							x={getRingRadiusForDepth(depth) + 12}
							y={-10}
							class="agent-canvas__ring-label"
						>
							Depth {String(depth).padStart(2, '0')}
						</text>
					{/each}
				</g>
			{/if}

			<g class="agent-canvas__connections">
				{#each store.edges as segment (segment.childId + segment.parentId)}
					<path
						d={getConnectionPath(segment)}
						data-connection-child-id={segment.childId}
						class="agent-canvas__connection"
					></path>
				{/each}
				{#each store.mergedEdges as segment (`${segment.mergedNodeId}-${segment.targetNodeId}`)}
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
				{#each store.nodes as node (node.id)}
					{@const placement = placementById.get(node.id)}
					{#if placement}
						<Node
							{node}
							x={placement.x}
							y={placement.y}
							isSelected={store.selectedNodeId === node.id}
							isMergeTarget={mergeHoverId === node.id}
							isMergeSource={mergeSourceId === node.id}
							onSelect={(id) => store.select(id)}
							onPointerDown={handleNodePointerDown}
						/>
					{/if}
				{/each}
			</g>
		</g>
	</svg>

	{#if store.nodes.length === 0}
		<div class="empty">
			<p class="eyebrow">Empty graph</p>
			<p class="hint">Open the side controls and click <strong>New root</strong> to begin.</p>
		</div>
	{/if}

	{#if selectedNodeForPopover && selectedScreenPos}
		<NodePromptPopover
			{store}
			node={selectedNodeForPopover}
			screenX={selectedScreenPos.x}
			screenY={selectedScreenPos.y}
		/>
	{/if}
</div>

<style>
	.agent-canvas {
		position: absolute;
		inset: 0;
		overflow: hidden;
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

	.empty {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		text-align: center;
		color: var(--color-text-muted);
		pointer-events: none;
	}
	.eyebrow {
		font-size: 0.7rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.hint {
		max-width: 22rem;
		font-size: 0.85rem;
		line-height: 1.5;
		color: var(--color-text-muted);
	}
	.hint strong {
		color: var(--color-text);
	}
</style>
