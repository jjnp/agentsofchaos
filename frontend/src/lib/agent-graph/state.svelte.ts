import type { AgentNode, AgentNodeId, AgentNodePlacement, LayoutMode } from './types';

export type AgentGraphState = {
	readonly nodes: readonly AgentNode[];
	setNodes(nextNodes: readonly AgentNode[]): void;
	readonly placements: readonly AgentNodePlacement[];
	setPlacements(nextPlacements: readonly AgentNodePlacement[]): void;
	readonly activeLayoutMode: LayoutMode;
	setActiveLayoutMode(nextLayoutMode: LayoutMode): void;
	readonly selectedNodeId: AgentNodeId | null;
	setSelectedNodeId(nextSelectedNodeId: AgentNodeId | null): void;
	isNodeDetailsVisible(nodeId: AgentNodeId): boolean;
	toggleNodeDetails(nodeId: AgentNodeId): void;
	setAllNodeDetailsVisibility(isVisible: boolean): void;
	readonly showNodeDetailsForAll: boolean;
};

const getVisibleNodeDetailsIds = (nodes: readonly AgentNode[], visibleByDefault: boolean) =>
	visibleByDefault ? nodes.map((node) => node.id) : [];

export const createAgentGraphState = (
	initialNodes: readonly AgentNode[],
	initialPlacements: readonly AgentNodePlacement[],
	initialSelectedNodeId: AgentNodeId | null,
	initialLayoutMode: LayoutMode,
	initialShowNodeDetails = true
): AgentGraphState => {
	let nodes = $state<readonly AgentNode[]>(initialNodes);
	let placements = $state<readonly AgentNodePlacement[]>(initialPlacements);
	let selectedNodeId = $state<AgentNodeId | null>(initialSelectedNodeId);
	let activeLayoutMode = $state<LayoutMode>(initialLayoutMode);
	let visibleNodeDetailsIds = $state<readonly AgentNodeId[]>(
		getVisibleNodeDetailsIds(initialNodes, initialShowNodeDetails)
	);

	return {
		get nodes() {
			return nodes;
		},
		setNodes(nextNodes: readonly AgentNode[]) {
			nodes = nextNodes;
			visibleNodeDetailsIds = visibleNodeDetailsIds.filter((nodeId) =>
				nextNodes.some((node) => node.id === nodeId)
			);
		},
		get placements() {
			return placements;
		},
		setPlacements(nextPlacements: readonly AgentNodePlacement[]) {
			placements = nextPlacements;
		},
		get activeLayoutMode() {
			return activeLayoutMode;
		},
		setActiveLayoutMode(nextLayoutMode: LayoutMode) {
			activeLayoutMode = nextLayoutMode;
		},
		get selectedNodeId() {
			return selectedNodeId;
		},
		setSelectedNodeId(nextSelectedNodeId: AgentNodeId | null) {
			selectedNodeId = nextSelectedNodeId;
		},
		isNodeDetailsVisible(nodeId: AgentNodeId) {
			return visibleNodeDetailsIds.includes(nodeId);
		},
		toggleNodeDetails(nodeId: AgentNodeId) {
			visibleNodeDetailsIds = visibleNodeDetailsIds.includes(nodeId)
				? visibleNodeDetailsIds.filter((visibleNodeId) => visibleNodeId !== nodeId)
				: [...visibleNodeDetailsIds, nodeId];
		},
		setAllNodeDetailsVisibility(isVisible: boolean) {
			visibleNodeDetailsIds = getVisibleNodeDetailsIds(nodes, isVisible);
		},
		get showNodeDetailsForAll() {
			return nodes.length > 0 && nodes.every((node) => visibleNodeDetailsIds.includes(node.id));
		}
	};
};
