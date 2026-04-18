import type { AgentNode, AgentNodeId, AgentNodePlacement, LayoutMode } from './types';

export type AgentGraphState = ReturnType<typeof createAgentGraphState>;

export const createAgentGraphState = (
	initialNodes: readonly AgentNode[],
	initialPlacements: readonly AgentNodePlacement[],
	initialSelectedNodeId: AgentNodeId | null,
	initialLayoutMode: LayoutMode
) => {
	let nodes = $state<readonly AgentNode[]>(initialNodes);
	let placements = $state<readonly AgentNodePlacement[]>(initialPlacements);
	let selectedNodeId = $state<AgentNodeId | null>(initialSelectedNodeId);
	let activeLayoutMode = $state<LayoutMode>(initialLayoutMode);

	return {
		get nodes() {
			return nodes;
		},
		setNodes(nextNodes: readonly AgentNode[]) {
			nodes = nextNodes;
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
		}
	};
};
