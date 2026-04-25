import type { Node, NodeId } from '../orchestrator/contracts';

export const layoutModes = ['rings', 'tree', 'force'] as const;
export type LayoutMode = (typeof layoutModes)[number];

export interface NodePlacement {
	readonly nodeId: NodeId;
	readonly x: number;
	readonly y: number;
}

export interface ConnectionSegment {
	readonly childId: NodeId;
	readonly parentId: NodeId;
	readonly x1: number;
	readonly y1: number;
	readonly x2: number;
	readonly y2: number;
}

export interface MergedConnectionSegment {
	readonly mergedNodeId: NodeId;
	readonly targetNodeId: NodeId;
	readonly x1: number;
	readonly y1: number;
	readonly x2: number;
	readonly y2: number;
}

export interface CanvasViewport {
	readonly x: number;
	readonly y: number;
	readonly scale: number;
}

export interface CanvasPoint {
	readonly x: number;
	readonly y: number;
}

/**
 * Nodes have `parent_node_ids: NodeId[]`. The convention used by the orchestrator (see MergeApplicationService) is parent_node_ids = (source, target)
 * for merges. We treat the LAST parent as the structural parent for layout
 * (the branch being extended) and any earlier parents as merge-source connections.
 */
export function structuralParentId(node: Node): NodeId | null {
	if (node.parent_node_ids.length === 0) {
		return null;
	}
	return node.parent_node_ids[node.parent_node_ids.length - 1];
}

export function mergeSourceIds(node: Node): readonly NodeId[] {
	if (node.parent_node_ids.length <= 1) {
		return [];
	}
	return node.parent_node_ids.slice(0, -1);
}
