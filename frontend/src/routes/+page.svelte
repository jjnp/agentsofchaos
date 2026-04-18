<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { computeLayoutPlacements } from '$lib/agent-graph/layout';
	import { fork, forkPromptSchema, merge } from '$lib/agent-graph/api';
	import { demoAgentNodePlacements, demoAgentNodes } from '$lib/agent-graph/fixtures';
	import AgentCanvas from '$lib/components/agent-graph/AgentCanvas.svelte';
	import AgentNodeViewSidebar from '$lib/components/agent-graph/AgentNodeViewSidebar.svelte';
	import AgentCanvasSidebar from '$lib/components/agent-graph/AgentCanvasSidebar.svelte';
	import { createOrchestratorClient } from '$lib/orchestrator/client';
	import {
		subscribeToOrchestratorEvents,
		type OrchestratorEventStreamStatus
	} from '$lib/orchestrator/events';
	import type { OrchestratorState } from '$lib/orchestrator/types';
	import type { ControlOption } from '$lib/components/primitives/types';
	import {
		createAgentNodePlacement,
		layoutModes,
		type AgentNode,
		type AgentNodeId,
		type AgentNodePlacement,
		type LayoutMode
	} from '$lib/agent-graph/types';
	import { safeParse } from 'valibot';

	const layoutModeOptions: readonly ControlOption[] = layoutModes.map((mode) => ({
		value: mode,
		label: mode === 'rings' ? 'Concentric rings' : mode === 'tree' ? 'Tree' : 'Force'
	}));

	const initialSelectedNodeId = demoAgentNodes[4]?.id ?? demoAgentNodes[0]?.id ?? null;

	let nodes = $state<readonly AgentNode[]>([...demoAgentNodes]);
	let basePlacements = $state<readonly AgentNodePlacement[]>([...demoAgentNodePlacements]);
	let activeLayoutMode = $state<LayoutMode>('rings');
	let showNodeDetailsForAll = $state(true);
	let selectedNodeId = $state<AgentNodeId | null>(initialSelectedNodeId);
	let nodeViewPrompt = $state('');
	const isNodeViewOpen = true;
	let isSidebarOpen = $state(true);
	let orchestratorState = $state<OrchestratorState | null>(null);
	let orchestratorLoadStatus = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');
	let orchestratorStreamStatus = $state<OrchestratorEventStreamStatus>('closed');
	let orchestratorError = $state<string | null>(null);

	const orchestratorClient = createOrchestratorClient();

	const activePlacements = $derived(
		computeLayoutPlacements({
			nodes,
			basePlacements,
			mode: activeLayoutMode
		})
	);
	const selectedNode = $derived(nodes.find((node) => node.id === selectedNodeId) ?? null);

	const getChildPlacement = (
		parentNodeId: AgentNodeId,
		childNodeId: AgentNodeId,
		currentPlacements: readonly AgentNodePlacement[],
		allNodes: readonly AgentNode[]
	) => {
		const parentPlacement =
			currentPlacements.find((placement) => placement.nodeId === parentNodeId) ??
			basePlacements.find((placement) => placement.nodeId === parentNodeId) ??
			createAgentNodePlacement({ nodeId: parentNodeId, x: 0, y: 0 });
		const siblingCount = allNodes.filter((node) => node.parentId === parentNodeId).length;
		const siblingOffset = siblingCount * 32;

		return createAgentNodePlacement({
			nodeId: childNodeId,
			x: parentPlacement.x + 180,
			y: parentPlacement.y + 108 + siblingOffset
		});
	};

	const handleForkSubmit = () => {
		if (!selectedNode) {
			return;
		}

		const parsedPrompt = safeParse(forkPromptSchema, nodeViewPrompt);
		if (!parsedPrompt.success) {
			return;
		}

		const nextNode = fork(selectedNode, parsedPrompt.output);
		const nextPlacement = getChildPlacement(selectedNode.id, nextNode.id, activePlacements, nodes);

		nodes = [...nodes, nextNode];
		basePlacements = [...basePlacements, nextPlacement];
		selectedNodeId = nextNode.id;
		nodeViewPrompt = '';
	};

	const handleMerge = (sourceNodeId: AgentNodeId, targetNodeId: AgentNodeId) => {
		const sourceNode = nodes.find((node) => node.id === sourceNodeId);
		const targetNode = nodes.find((node) => node.id === targetNodeId) ?? null;
		if (!sourceNode || !targetNode) {
			return;
		}

		const mergedNode = merge(targetNode, sourceNode);
		const mergedPlacement = getChildPlacement(
			targetNode.id,
			mergedNode.id,
			activePlacements,
			nodes
		);

		nodes = [...nodes, mergedNode];
		basePlacements = [...basePlacements, mergedPlacement];
		selectedNodeId = mergedNode.id;
	};

	const refreshOrchestratorState = async () => {
		orchestratorLoadStatus = 'loading';
		orchestratorError = null;

		try {
			orchestratorState = await orchestratorClient.getState();
			orchestratorLoadStatus = 'ready';
		} catch (error) {
			orchestratorLoadStatus = 'error';
			orchestratorError =
				error instanceof Error ? error.message : 'Failed to load orchestrator state.';
		}
	};

	onMount(() => {
		if (!browser) {
			return;
		}

		void refreshOrchestratorState();

		const subscription = subscribeToOrchestratorEvents({
			onEvent: (event) => {
				if (event.type === 'grid_boot') {
					orchestratorState = orchestratorState
						? {
								...orchestratorState,
								sessionId: event.session,
								model: event.model,
								mergeModel: event.mergeModel
							}
						: orchestratorState;
				}

				if (
					event.type === 'instance_created' ||
					event.type === 'instance_stopped' ||
					event.type === 'fork_complete' ||
					event.type === 'merge_complete' ||
					event.type === 'merge_integration_created' ||
					event.type === 'session_ready'
				) {
					void refreshOrchestratorState();
				}
			},
			onStatusChange: (status) => {
				orchestratorStreamStatus = status;
			},
			onError: (error) => {
				orchestratorError = error.message;
			}
		});

		return () => {
			subscription.close();
		};
	});
</script>

<svelte:head>
	<title>Agents of Chaos</title>
	<meta name="description" content="Graph canvas foundation for agent nodes and connections." />
</svelte:head>

<div class="canvas-page">
	<AgentNodeViewSidebar
		{selectedNode}
		isOpen={isNodeViewOpen}
		bind:prompt={nodeViewPrompt}
		onSubmit={handleForkSubmit}
	/>

	<AgentCanvas
		bind:activeLayoutMode
		{selectedNodeId}
		onSelectedNodeChange={(nodeId) => {
			selectedNodeId = nodeId;
		}}
		onMerge={handleMerge}
		{showNodeDetailsForAll}
		{nodes}
		placements={activePlacements}
		class="h-screen rounded-none border-0"
	/>

	<AgentCanvasSidebar
		bind:activeLayoutMode
		bind:showNodeDetailsForAll
		bind:isOpen={isSidebarOpen}
		{layoutModeOptions}
		{orchestratorState}
		{orchestratorLoadStatus}
		{orchestratorStreamStatus}
		{orchestratorError}
	/>
</div>
