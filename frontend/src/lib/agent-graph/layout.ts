import type { AgentNode, AgentNodeId, AgentNodePlacement } from './types';

export type CanvasViewport = Readonly<{
	x: number;
	y: number;
	scale: number;
}>;

export type ConnectionSegment = Readonly<{
	childId: AgentNodeId;
	parentId: AgentNodeId;
	x1: number;
	y1: number;
	x2: number;
	y2: number;
}>;

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

export const getViewportAfterZoom = ({
	viewport,
	deltaY,
	pointer,
	minScale,
	maxScale
}: {
	viewport: CanvasViewport;
	deltaY: number;
	pointer: Readonly<{ x: number; y: number }>;
	minScale: number;
	maxScale: number;
}): CanvasViewport => {
	const zoomFactor = deltaY < 0 ? 1.12 : 0.88;
	const nextScale = clampScale(viewport.scale * zoomFactor, minScale, maxScale);
	const scaleRatio = nextScale / viewport.scale;

	return {
		scale: nextScale,
		x: pointer.x - (pointer.x - viewport.x) * scaleRatio,
		y: pointer.y - (pointer.y - viewport.y) * scaleRatio
	};
};

export const getCanvasTransform = (
	viewport: CanvasViewport,
	canvasSize: { width: number; height: number }
) =>
	`translate(${canvasSize.width / 2 + viewport.x} ${canvasSize.height / 2 + viewport.y}) scale(${viewport.scale})`;

export const getConnectionPath = (segment: ConnectionSegment) => {
	const controlX = (segment.x1 + segment.x2) / 2;
	const controlY = (segment.y1 + segment.y2) / 2;

	return `M ${segment.x1} ${segment.y1} Q ${controlX} ${controlY} ${segment.x2} ${segment.y2}`;
};
