import type { NodeId } from '../orchestrator/contracts';

import {
	mergeSourceIds,
	structuralParentId,
	type CanvasPoint,
	type CanvasViewport,
	type ConnectionSegment,
	type GraphNode,
	type LayoutMode,
	type MergedConnectionSegment,
	type NodePlacement
} from './types';

const RING_RADIUS_STEP = 220;
const RING_CHILD_SPREAD = 0.78;
const MULTI_ROOT_RING_RADIUS = 280;
const TREE_X_STEP = 240;
const TREE_Y_STEP = 180;
const ROOT_NODE_CONNECTION_OFFSET = 30;
const CHILD_NODE_CONNECTION_OFFSET = 24;

export const clampScale = (scale: number, minScale: number, maxScale: number) =>
	Math.min(Math.max(scale, minScale), maxScale);

const placementMap = (placements: readonly NodePlacement[]) =>
	new Map<NodeId, NodePlacement>(placements.map((p) => [p.nodeId, p]));

const getChildrenMap = (nodes: readonly GraphNode[]) => {
	const map = new Map<NodeId | null, GraphNode[]>();
	for (const node of nodes) {
		const parent = structuralParentId(node);
		const siblings = map.get(parent) ?? [];
		siblings.push(node);
		map.set(parent, siblings);
	}
	return map;
};

export function getNodeDepth(target: GraphNode, byId: ReadonlyMap<NodeId, GraphNode>): number {
	let depth = 0;
	let parent = structuralParentId(target);
	const visited = new Set<NodeId>();
	while (parent !== null) {
		if (visited.has(parent)) break;
		visited.add(parent);
		const parentNode = byId.get(parent);
		if (!parentNode) break;
		depth += 1;
		parent = structuralParentId(parentNode);
	}
	return depth;
}

export function getMaxNodeDepth(nodes: readonly GraphNode[]): number {
	const byId = new Map<NodeId, GraphNode>(nodes.map((n) => [n.id, n]));
	return nodes.reduce((max, node) => Math.max(max, getNodeDepth(node, byId)), 0);
}

export const getRingRadiusForDepth = (depth: number) => depth * RING_RADIUS_STEP;

function getRootOrigin(index: number, count: number): CanvasPoint {
	if (count <= 1) {
		return { x: 0, y: 0 };
	}
	const radius = Math.max(MULTI_ROOT_RING_RADIUS, ((count - 1) * RING_RADIUS_STEP) / 2);
	const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count;
	return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

function placeRingChildren(
	parentId: NodeId,
	childrenMap: Map<NodeId | null, GraphNode[]>,
	placements: NodePlacement[],
	origin: CanvasPoint,
	radius: number,
	startAngle: number,
	endAngle: number
): void {
	const children = childrenMap.get(parentId) ?? [];
	if (children.length === 0) return;
	const totalSpan = (endAngle - startAngle) * RING_CHILD_SPREAD;
	const centeredStart = startAngle + (endAngle - startAngle - totalSpan) / 2;
	const angleStep = totalSpan / children.length;
	for (const [index, child] of children.entries()) {
		const angle = centeredStart + angleStep * index + angleStep / 2;
		placements.push({
			nodeId: child.id,
			x: origin.x + Math.cos(angle) * radius,
			y: origin.y + Math.sin(angle) * radius
		});
		placeRingChildren(
			child.id,
			childrenMap,
			placements,
			origin,
			radius + RING_RADIUS_STEP,
			angle - angleStep / 2,
			angle + angleStep / 2
		);
	}
}

export function computeRingLayout(nodes: readonly GraphNode[]): NodePlacement[] {
	const childrenMap = getChildrenMap(nodes);
	const placements: NodePlacement[] = [];
	const roots = childrenMap.get(null) ?? [];
	for (const [index, root] of roots.entries()) {
		const origin = getRootOrigin(index, roots.length);
		placements.push({ nodeId: root.id, x: origin.x, y: origin.y });
		placeRingChildren(
			root.id,
			childrenMap,
			placements,
			origin,
			RING_RADIUS_STEP,
			-Math.PI,
			Math.PI
		);
	}
	return placements;
}

export function computeTreeLayout(nodes: readonly GraphNode[]): NodePlacement[] {
	const childrenMap = getChildrenMap(nodes);
	const queue: Array<{ node: GraphNode; depth: number }> = (childrenMap.get(null) ?? []).map(
		(node) => ({ node, depth: 0 })
	);
	const levels: GraphNode[][] = [];
	while (queue.length > 0) {
		const current = queue.shift();
		if (!current) continue;
		levels[current.depth] ??= [];
		levels[current.depth].push(current.node);
		for (const child of childrenMap.get(current.node.id) ?? []) {
			queue.push({ node: child, depth: current.depth + 1 });
		}
	}
	return levels.flatMap((levelNodes, depth) => {
		const totalWidth = (levelNodes.length - 1) * TREE_X_STEP;
		return levelNodes.map((node, index) => ({
			nodeId: node.id,
			x: index * TREE_X_STEP - totalWidth / 2,
			y: depth * TREE_Y_STEP
		}));
	});
}

export function computeForceLayout(
	nodes: readonly GraphNode[],
	basePlacements: readonly NodePlacement[]
): NodePlacement[] {
	const baseLookup = placementMap(basePlacements);
	type MutablePosition = { x: number; y: number };
	const positions = new Map<NodeId, MutablePosition>(
		nodes.map((node, index) => {
			const base = baseLookup.get(node.id);
			return [
				node.id,
				{
					x: base?.x ?? Math.cos(index) * RING_RADIUS_STEP,
					y: base?.y ?? Math.sin(index) * RING_RADIUS_STEP
				}
			];
		})
	);
	for (let iteration = 0; iteration < 28; iteration += 1) {
		for (const node of nodes) {
			const current = positions.get(node.id);
			if (!current) continue;
			let fx = 0;
			let fy = 0;
			for (const other of nodes) {
				if (other.id === node.id) continue;
				const otherPosition = positions.get(other.id);
				if (!otherPosition) continue;
				const dx = current.x - otherPosition.x;
				const dy = current.y - otherPosition.y;
				const distSq = Math.max(dx * dx + dy * dy, 1);
				const repulsion = 16000 / distSq;
				fx += (dx / Math.sqrt(distSq)) * repulsion;
				fy += (dy / Math.sqrt(distSq)) * repulsion;
			}
			const parentId = structuralParentId(node);
			if (parentId) {
				const parent = positions.get(parentId);
				if (parent) {
					fx += (parent.x - current.x) * 0.05;
					fy += (parent.y - current.y) * 0.05;
				}
			}
			current.x += fx * 0.01;
			current.y += fy * 0.01;
		}
	}
	for (const node of nodes) {
		if (structuralParentId(node) === null) {
			const root = positions.get(node.id);
			if (root) {
				root.x = 0;
				root.y = 0;
			}
		}
	}
	return nodes.map((node) => {
		const p = positions.get(node.id) ?? { x: 0, y: 0 };
		return { nodeId: node.id, x: p.x, y: p.y };
	});
}

export function computeLayoutPlacements({
	nodes,
	basePlacements,
	mode
}: {
	nodes: readonly GraphNode[];
	basePlacements: readonly NodePlacement[];
	mode: LayoutMode;
}): NodePlacement[] {
	switch (mode) {
		case 'tree':
			return computeTreeLayout(nodes);
		case 'force':
			return computeForceLayout(nodes, basePlacements);
		case 'rings':
		default:
			return computeRingLayout(nodes);
	}
}

export function getConnectionSegments(
	nodes: readonly GraphNode[],
	placements: readonly NodePlacement[]
): ConnectionSegment[] {
	const lookup = placementMap(placements);
	return nodes.flatMap((node) => {
		const parentId = structuralParentId(node);
		if (!parentId) return [];
		const childPlacement = lookup.get(node.id);
		const parentPlacement = lookup.get(parentId);
		if (!childPlacement || !parentPlacement) return [];
		return [
			{
				childId: node.id,
				parentId,
				x1: parentPlacement.x,
				y1: parentPlacement.y,
				x2: childPlacement.x,
				y2: childPlacement.y
			}
		];
	});
}

const getNodeConnectionOffset = (node: GraphNode) =>
	structuralParentId(node) === null
		? ROOT_NODE_CONNECTION_OFFSET
		: CHILD_NODE_CONNECTION_OFFSET;

function trimSegment(
	start: CanvasPoint,
	end: CanvasPoint,
	startOffset: number,
	endOffset: number
): { x1: number; y1: number; x2: number; y2: number } | null {
	const dx = end.x - start.x;
	const dy = end.y - start.y;
	const distance = Math.hypot(dx, dy);
	if (distance <= startOffset + endOffset) return null;
	const ux = dx / distance;
	const uy = dy / distance;
	return {
		x1: start.x + ux * startOffset,
		y1: start.y + uy * startOffset,
		x2: end.x - ux * endOffset,
		y2: end.y - uy * endOffset
	};
}

export function getMergedConnectionSegments(
	nodes: readonly GraphNode[],
	placements: readonly NodePlacement[]
): MergedConnectionSegment[] {
	const lookup = placementMap(placements);
	const byId = new Map<NodeId, GraphNode>(nodes.map((n) => [n.id, n]));
	return nodes.flatMap((node) => {
		const targetPlacement = lookup.get(node.id);
		if (!targetPlacement) return [];
		return mergeSourceIds(node).flatMap((mergedNodeId) => {
			const mergedNode = byId.get(mergedNodeId);
			const mergedPlacement = lookup.get(mergedNodeId);
			if (!mergedNode || !mergedPlacement) return [];
			const trimmed = trimSegment(
				mergedPlacement,
				targetPlacement,
				getNodeConnectionOffset(mergedNode),
				getNodeConnectionOffset(node)
			);
			if (!trimmed) return [];
			return [
				{
					mergedNodeId,
					targetNodeId: node.id,
					...trimmed
				}
			];
		});
	});
}

export function getViewportAfterZoom({
	viewport,
	deltaY,
	pointer,
	canvasSize,
	minScale,
	maxScale
}: {
	viewport: CanvasViewport;
	deltaY: number;
	pointer: CanvasPoint;
	canvasSize: { readonly width: number; readonly height: number };
	minScale: number;
	maxScale: number;
}): CanvasViewport {
	const zoom = deltaY < 0 ? 1.12 : 0.88;
	const nextScale = clampScale(viewport.scale * zoom, minScale, maxScale);
	const ratio = nextScale / viewport.scale;
	const tx = canvasSize.width / 2 + viewport.x;
	const ty = canvasSize.height / 2 + viewport.y;
	const nextTx = pointer.x - (pointer.x - tx) * ratio;
	const nextTy = pointer.y - (pointer.y - ty) * ratio;
	return {
		scale: nextScale,
		x: nextTx - canvasSize.width / 2,
		y: nextTy - canvasSize.height / 2
	};
}

export const getCanvasTransform = (
	viewport: CanvasViewport,
	canvasSize: { readonly width: number; readonly height: number }
) =>
	`translate(${canvasSize.width / 2 + viewport.x} ${canvasSize.height / 2 + viewport.y}) scale(${viewport.scale})`;

export const getCanvasPointFromScreen = ({
	pointer,
	viewport,
	canvasSize
}: {
	pointer: CanvasPoint;
	viewport: CanvasViewport;
	canvasSize: { readonly width: number; readonly height: number };
}): CanvasPoint => ({
	x: (pointer.x - canvasSize.width / 2 - viewport.x) / viewport.scale,
	y: (pointer.y - canvasSize.height / 2 - viewport.y) / viewport.scale
});

export const getConnectionPath = (segment: ConnectionSegment) => {
	const cx = (segment.x1 + segment.x2) / 2;
	const cy = (segment.y1 + segment.y2) / 2;
	return `M ${segment.x1} ${segment.y1} Q ${cx} ${cy} ${segment.x2} ${segment.y2}`;
};

export const getStraightConnectionPath = (segment: ConnectionSegment | MergedConnectionSegment) =>
	`M ${segment.x1} ${segment.y1} L ${segment.x2} ${segment.y2}`;

export const getMergePreviewPath = (start: CanvasPoint, end: CanvasPoint) => {
	const dx = end.x - start.x;
	const dy = end.y - start.y;
	const distance = Math.hypot(dx, dy);
	const mx = (start.x + end.x) / 2;
	const my = (start.y + end.y) / 2;
	const nx = distance === 0 ? 0 : -dy / distance;
	const ny = distance === 0 ? -1 : dx / distance;
	const curve = Math.min(Math.max(distance * 0.18, 28), 72);
	const cx = mx + nx * curve;
	const cy = my + ny * curve;
	return `M ${start.x} ${start.y} Q ${cx} ${cy} ${end.x} ${end.y}`;
};

export function computeBounds(placements: readonly NodePlacement[]): {
	minX: number;
	maxX: number;
	minY: number;
	maxY: number;
} {
	if (placements.length === 0) {
		return { minX: 0, maxX: 0, minY: 0, maxY: 0 };
	}
	let minX = Infinity;
	let maxX = -Infinity;
	let minY = Infinity;
	let maxY = -Infinity;
	for (const p of placements) {
		if (p.x < minX) minX = p.x;
		if (p.x > maxX) maxX = p.x;
		if (p.y < minY) minY = p.y;
		if (p.y > maxY) maxY = p.y;
	}
	return { minX, maxX, minY, maxY };
}
