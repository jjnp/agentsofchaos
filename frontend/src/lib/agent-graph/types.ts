import type { Node, NodeId } from '../orchestrator/contracts';

export interface PendingNode {
	readonly pending: true;
	readonly id: NodeId;
	readonly project_id: Node['project_id'];
	readonly kind: Extract<Node['kind'], 'prompt' | 'resolution'>;
	readonly parent_node_ids: readonly NodeId[];
	readonly status: Extract<Node['status'], 'running' | 'failed' | 'cancelled'>;
	readonly title: string;
	readonly created_at: string;
	readonly originating_run_id: NonNullable<Node['originating_run_id']>;
}

export type GraphNode = Node | PendingNode;

export function isPendingNode(node: GraphNode): node is PendingNode {
	return 'pending' in node && node.pending === true;
}

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
export function structuralParentId(node: GraphNode): NodeId | null {
	if (node.parent_node_ids.length === 0) {
		return null;
	}
	return node.parent_node_ids[node.parent_node_ids.length - 1];
}

export function mergeSourceIds(node: GraphNode): readonly NodeId[] {
	if (node.parent_node_ids.length <= 1) {
		return [];
	}
	return node.parent_node_ids.slice(0, -1);
}
