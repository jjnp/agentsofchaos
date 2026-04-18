import { createAgentNodePlacement } from './types';
import type { AgentNode, AgentNodeId, AgentNodePlacement, LayoutMode } from './types';

export type CanvasViewport = Readonly<{
	x: number;
	y: number;
	scale: number;
}>;

export type CanvasPoint = Readonly<{
	x: number;
	y: number;
}>;

export type ConnectionSegment = Readonly<{
	childId: AgentNodeId;
	parentId: AgentNodeId;
	x1: number;
	y1: number;
	x2: number;
	y2: number;
}>;

export type MergedConnectionSegment = Readonly<{
	mergedNodeId: AgentNodeId;
	targetNodeId: AgentNodeId;
	x1: number;
	y1: number;
	x2: number;
	y2: number;
}>;

const RING_RADIUS_STEP = 220;
const RING_CHILD_SPREAD = 0.78;
const MULTI_ROOT_RING_RADIUS = 280;
const TREE_X_STEP = 240;
const TREE_Y_STEP = 180;
const ROOT_NODE_CONNECTION_OFFSET = 30;
const CHILD_NODE_CONNECTION_OFFSET = 24;

export const clampScale = (scale: number, minScale: number, maxScale: number) =>
	Math.min(Math.max(scale, minScale), maxScale);

export const getPlacementLookup = (placements: readonly AgentNodePlacement[]) =>
	new Map(placements.map((placement) => [placement.nodeId, placement]));

export const getConnectionSegments = (
	nodes: readonly AgentNode[],
	placements: readonly AgentNodePlacement[]
): ConnectionSegment[] => {
	const placementLookup = getPlacementLookup(placements);

	return nodes.flatMap((node) => {
		if (!node.parentId) {
			return [];
		}

		const parentPlacement = placementLookup.get(node.parentId);
		const childPlacement = placementLookup.get(node.id);
		if (!parentPlacement || !childPlacement) {
			return [];
		}

		return [
			{
				childId: node.id,
				parentId: node.parentId,
				x1: parentPlacement.x,
				y1: parentPlacement.y,
				x2: childPlacement.x,
				y2: childPlacement.y
			}
		];
	});
};

export const getMergedConnectionSegments = (
	nodes: readonly AgentNode[],
	placements: readonly AgentNodePlacement[]
): MergedConnectionSegment[] => {
	const placementLookup = getPlacementLookup(placements);
	const nodeLookup = new Map(nodes.map((node) => [node.id, node]));

	return nodes.flatMap((node) => {
		const targetPlacement = placementLookup.get(node.id);
		if (!targetPlacement) {
			return [];
		}

		return node.mergedNodes.flatMap((mergedNodeId) => {
			const mergedNode = nodeLookup.get(mergedNodeId);
			const mergedNodePlacement = placementLookup.get(mergedNodeId);
			if (!mergedNodePlacement || !mergedNode) {
				return [];
			}

			const trimmedSegment = getTrimmedLineSegment({
				start: mergedNodePlacement,
				end: targetPlacement,
				startOffset: getNodeConnectionOffset(mergedNode),
				endOffset: getNodeConnectionOffset(node)
			});
			if (!trimmedSegment) {
				return [];
			}

			return [
				{
					mergedNodeId,
					targetNodeId: node.id,
					x1: trimmedSegment.x1,
					y1: trimmedSegment.y1,
					x2: trimmedSegment.x2,
					y2: trimmedSegment.y2
				}
			];
		});
	});
};

const getNodeConnectionOffset = (node: AgentNode) =>
	node.parentId === null ? ROOT_NODE_CONNECTION_OFFSET : CHILD_NODE_CONNECTION_OFFSET;

const getTrimmedLineSegment = ({
	start,
	end,
	startOffset,
	endOffset
}: {
	start: Readonly<{ x: number; y: number }>;
	end: Readonly<{ x: number; y: number }>;
	startOffset: number;
	endOffset: number;
}) => {
	const dx = end.x - start.x;
	const dy = end.y - start.y;
	const distance = Math.hypot(dx, dy);
	if (distance <= startOffset + endOffset) {
		return null;
	}

	const unitX = dx / distance;
	const unitY = dy / distance;

	return {
		x1: start.x + unitX * startOffset,
		y1: start.y + unitY * startOffset,
		x2: end.x - unitX * endOffset,
		y2: end.y - unitY * endOffset
	};
};

export const getNodeDepth = (targetNode: AgentNode, nodes: readonly AgentNode[]) => {
	const nodeLookup = new Map(nodes.map((node) => [node.id, node]));
	let depth = 0;
	let currentParentId = targetNode.parentId;

	while (currentParentId) {
		const parentNode = nodeLookup.get(currentParentId);
		if (!parentNode) {
			break;
		}

		depth += 1;
		currentParentId = parentNode.parentId;
	}

	return depth;
};

export const getMaxNodeDepth = (nodes: readonly AgentNode[]) =>
	nodes.reduce((maxDepth, node) => Math.max(maxDepth, getNodeDepth(node, nodes)), 0);

export const getViewportAfterZoom = ({
	viewport,
	deltaY,
	pointer,
	canvasSize,
	minScale,
	maxScale
}: {
	viewport: CanvasViewport;
	deltaY: number;
	pointer: Readonly<{ x: number; y: number }>;
	canvasSize: Readonly<{ width: number; height: number }>;
	minScale: number;
	maxScale: number;
}): CanvasViewport => {
	const zoomFactor = deltaY < 0 ? 1.12 : 0.88;
	const nextScale = clampScale(viewport.scale * zoomFactor, minScale, maxScale);
	const scaleRatio = nextScale / viewport.scale;
	const currentTranslateX = canvasSize.width / 2 + viewport.x;
	const currentTranslateY = canvasSize.height / 2 + viewport.y;
	const nextTranslateX = pointer.x - (pointer.x - currentTranslateX) * scaleRatio;
	const nextTranslateY = pointer.y - (pointer.y - currentTranslateY) * scaleRatio;

	return {
		scale: nextScale,
		x: nextTranslateX - canvasSize.width / 2,
		y: nextTranslateY - canvasSize.height / 2
	};
};

export const getCanvasTransform = (
	viewport: CanvasViewport,
	canvasSize: { width: number; height: number }
) =>
	`translate(${canvasSize.width / 2 + viewport.x} ${canvasSize.height / 2 + viewport.y}) scale(${viewport.scale})`;

export const getCanvasPointFromScreen = ({
	pointer,
	viewport,
	canvasSize
}: {
	pointer: CanvasPoint;
	viewport: CanvasViewport;
	canvasSize: Readonly<{ width: number; height: number }>;
}): CanvasPoint => ({
	x: (pointer.x - canvasSize.width / 2 - viewport.x) / viewport.scale,
	y: (pointer.y - canvasSize.height / 2 - viewport.y) / viewport.scale
});

const getChildrenMap = (nodes: readonly AgentNode[]) => {
	const childrenMap = new Map<AgentNodeId | null, AgentNode[]>();

	for (const node of nodes) {
		const siblings = childrenMap.get(node.parentId) ?? [];
		siblings.push(node);
		childrenMap.set(node.parentId, siblings);
	}

	return childrenMap;
};

export const computeLayoutPlacements = ({
	nodes,
	basePlacements,
	mode
}: {
	nodes: readonly AgentNode[];
	basePlacements: readonly AgentNodePlacement[];
	mode: LayoutMode;
}) => {
	switch (mode) {
		case 'tree':
			return computeTreeLayout(nodes);
		case 'force':
			return computeForceLayout(nodes, basePlacements);
		case 'rings':
		default:
			return computeRingLayout(nodes);
	}
};

function getRootOrigin(index: number, count: number): { x: number; y: number } {
	if (count <= 1) {
		return { x: 0, y: 0 };
	}

	const radius = Math.max(MULTI_ROOT_RING_RADIUS, ((count - 1) * RING_RADIUS_STEP) / 2);
	const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count;
	return {
		x: Math.cos(angle) * radius,
		y: Math.sin(angle) * radius
	};
}

const computeRingLayout = (nodes: readonly AgentNode[]) => {
	const childrenMap = getChildrenMap(nodes);
	const placements: AgentNodePlacement[] = [];
	const roots = childrenMap.get(null) ?? [];

	for (const [index, root] of roots.entries()) {
		const origin = getRootOrigin(index, roots.length);
		placements.push(createAgentNodePlacement({ nodeId: root.id, x: origin.x, y: origin.y }));
		placeRingChildren({
			parentId: root.id,
			childrenMap,
			placements,
			origin,
			radius: RING_RADIUS_STEP,
			startAngle: -Math.PI,
			endAngle: Math.PI
		});
	}

	return placements;
};

const placeRingChildren = ({
	parentId,
	childrenMap,
	placements,
	origin,
	radius,
	startAngle,
	endAngle
}: {
	parentId: AgentNodeId;
	childrenMap: Map<AgentNodeId | null, AgentNode[]>;
	placements: AgentNodePlacement[];
	origin: Readonly<{ x: number; y: number }>;
	radius: number;
	startAngle: number;
	endAngle: number;
}) => {
	const children = childrenMap.get(parentId) ?? [];
	if (children.length === 0) {
		return;
	}

	const totalSpan = (endAngle - startAngle) * RING_CHILD_SPREAD;
	const centeredStartAngle = startAngle + (endAngle - startAngle - totalSpan) / 2;
	const angleStep = totalSpan / children.length;
	for (const [index, child] of children.entries()) {
		const angle = centeredStartAngle + angleStep * index + angleStep / 2;
		placements.push(
			createAgentNodePlacement({
				nodeId: child.id,
				x: origin.x + Math.cos(angle) * radius,
				y: origin.y + Math.sin(angle) * radius
			})
		);

		placeRingChildren({
			parentId: child.id,
			childrenMap,
			placements,
			origin,
			radius: radius + RING_RADIUS_STEP,
			startAngle: angle - angleStep / 2,
			endAngle: angle + angleStep / 2
		});
	}
};

const computeTreeLayout = (nodes: readonly AgentNode[]) => {
	const childrenMap = getChildrenMap(nodes);
	const queue = (childrenMap.get(null) ?? []).map((node) => ({ node, depth: 0 }));
	const levels: AgentNode[][] = [];

	while (queue.length > 0) {
		const current = queue.shift();
		if (!current) {
			continue;
		}

		levels[current.depth] ??= [];
		levels[current.depth].push(current.node);

		for (const child of childrenMap.get(current.node.id) ?? []) {
			queue.push({ node: child, depth: current.depth + 1 });
		}
	}

	return levels.flatMap((levelNodes, depth) => {
		const totalWidth = (levelNodes.length - 1) * TREE_X_STEP;
		return levelNodes.map((node, index) =>
			createAgentNodePlacement({
				nodeId: node.id,
				x: index * TREE_X_STEP - totalWidth / 2,
				y: depth * TREE_Y_STEP
			})
		);
	});
};

const computeForceLayout = (
	nodes: readonly AgentNode[],
	basePlacements: readonly AgentNodePlacement[]
) => {
	const baseLookup = getPlacementLookup(basePlacements);
	type MutablePosition = { x: number; y: number };
	const positions = new Map(
		nodes.map((node, index) => {
			const base = baseLookup.get(node.id);
			return [
				node.id,
				{
					x: base?.x ?? Math.cos(index) * RING_RADIUS_STEP,
					y: base?.y ?? Math.sin(index) * RING_RADIUS_STEP
				} satisfies MutablePosition
			] as const;
		})
	);

	for (let iteration = 0; iteration < 28; iteration += 1) {
		for (const node of nodes) {
			const current = positions.get(node.id);
			if (!current) {
				continue;
			}

			let forceX = 0;
			let forceY = 0;

			for (const otherNode of nodes) {
				if (otherNode.id === node.id) {
					continue;
				}

				const other = positions.get(otherNode.id);
				if (!other) {
					continue;
				}

				const dx = current.x - other.x;
				const dy = current.y - other.y;
				const distanceSquared = Math.max(dx * dx + dy * dy, 1);
				const repulsion = 16000 / distanceSquared;
				forceX += (dx / Math.sqrt(distanceSquared)) * repulsion;
				forceY += (dy / Math.sqrt(distanceSquared)) * repulsion;
			}

			if (node.parentId) {
				const parent = positions.get(node.parentId);
				if (parent) {
					forceX += (parent.x - current.x) * 0.05;
					forceY += (parent.y - current.y) * 0.05;
				}
			}

			current.x += forceX * 0.01;
			current.y += forceY * 0.01;
		}
	}

	for (const node of nodes) {
		if (node.parentId === null) {
			const rootPosition = positions.get(node.id);
			if (rootPosition) {
				rootPosition.x = 0;
				rootPosition.y = 0;
			}
		}
	}

	return nodes.map((node) => {
		const position = positions.get(node.id) ?? { x: 0, y: 0 };
		return createAgentNodePlacement({ nodeId: node.id, x: position.x, y: position.y });
	});
};

export const getRingRadiusForDepth = (depth: number) => depth * RING_RADIUS_STEP;

export const getConnectionPath = (segment: ConnectionSegment) => {
	const controlX = (segment.x1 + segment.x2) / 2;
	const controlY = (segment.y1 + segment.y2) / 2;

	return `M ${segment.x1} ${segment.y1} Q ${controlX} ${controlY} ${segment.x2} ${segment.y2}`;
};

export const getStraightConnectionPath = (segment: ConnectionSegment | MergedConnectionSegment) =>
	`M ${segment.x1} ${segment.y1} L ${segment.x2} ${segment.y2}`;

export const getMergePreviewPath = (start: CanvasPoint, end: CanvasPoint) => {
	const dx = end.x - start.x;
	const dy = end.y - start.y;
	const distance = Math.hypot(dx, dy);
	const midpointX = (start.x + end.x) / 2;
	const midpointY = (start.y + end.y) / 2;
	const normalX = distance === 0 ? 0 : -dy / distance;
	const normalY = distance === 0 ? -1 : dx / distance;
	const curveStrength = Math.min(Math.max(distance * 0.18, 28), 72);
	const controlX = midpointX + normalX * curveStrength;
	const controlY = midpointY + normalY * curveStrength;

	return `M ${start.x} ${start.y} Q ${controlX} ${controlY} ${end.x} ${end.y}`;
};
