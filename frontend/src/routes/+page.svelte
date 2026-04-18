<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { computeLayoutPlacements } from '$lib/agent-graph/layout';
	import AgentCanvas from '$lib/components/agent-graph/AgentCanvas.svelte';
	import AgentNodeViewSidebar from '$lib/components/agent-graph/AgentNodeViewSidebar.svelte';
	import AgentCanvasSidebar from '$lib/components/agent-graph/AgentCanvasSidebar.svelte';
	import type { ControlOption } from '$lib/components/primitives/types';
	import {
		getRuntimeNodeById,
		getSlotForNodeId,
		bootstrapOrchestratorGraph,
		createMissingArtifactState,
		createOrchestratorGraphState,
		createReadyArtifactState,
		markNodePromptQueued,
		materializeOrchestratorGraph,
		reduceOrchestratorGraphEvent,
		setForkPointArtifactState,
		setMergeContextArtifactState,
		setMergeDetailsArtifactState
	} from '$lib/orchestrator/graph';
	import { createOrchestratorClient, OrchestratorApiError } from '$lib/orchestrator/client';
	import {
		subscribeToOrchestratorEvents,
		type OrchestratorEventStreamStatus
	} from '$lib/orchestrator/events';
	import type { OrchestratorState } from '$lib/orchestrator/types';
	import { layoutModes, type AgentNodeId, type LayoutMode } from '$lib/agent-graph/types';
	import { safeParse } from 'valibot';
	import { forkPromptSchema } from '$lib/agent-graph/api';

	const layoutModeOptions: readonly ControlOption[] = layoutModes.map((mode) => ({
		value: mode,
		label: mode === 'rings' ? 'Concentric rings' : mode === 'tree' ? 'Tree' : 'Force'
	}));

	const orchestratorClient = createOrchestratorClient();

	let graphState = $state(createOrchestratorGraphState());
	let activeLayoutMode = $state<LayoutMode>('rings');
	let showNodeDetailsForAll = $state(true);
	let selectedNodeId = $state<AgentNodeId | null>(null);
	let nodeViewPrompt = $state('');
	const isNodeViewOpen = true;
	let isSidebarOpen = $state(true);
	let orchestratorLoadStatus = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');
	let orchestratorStreamStatus = $state<OrchestratorEventStreamStatus>('closed');
	let orchestratorError = $state<string | null>(null);

	const graph = $derived(materializeOrchestratorGraph(graphState));
	const activePlacements = $derived(
		computeLayoutPlacements({
			nodes: graph.nodes,
			basePlacements: graph.placements,
			mode: activeLayoutMode
		})
	);
	const selectedNode = $derived(getRuntimeNodeById(graphState, selectedNodeId));
	const sidebarOrchestratorState = $derived<OrchestratorState | null>(
		graphState.sessionId && graphState.model && graphState.mergeModel
			? {
					sessionId: graphState.sessionId,
					model: graphState.model,
					mergeModel: graphState.mergeModel,
					instanceCount: graphState.records.length,
					instances: graphState.records.map((record) => ({
						slot: record.backend.slot,
						label: record.backend.label,
						agentUuid: record.backend.agentUuid,
						containerName: record.backend.containerName,
						sessionId: record.backend.sessionId,
						sourceImage: record.backend.sourceImage ?? 'unknown',
						status: record.backend.instanceStatus,
						lastGitStatus: record.backend.gitStatus,
						lastForkPoint: record.artifacts.forkPoint.data
					}))
				}
			: null
	);

	const ensureSelectedNode = () => {
		if (selectedNodeId && graph.nodes.some((node) => node.id === selectedNodeId)) {
			return;
		}

		selectedNodeId = graph.nodes[0]?.id ?? null;
	};

	const fetchOptionalForkPointArtifact = async (slot: number) => {
		try {
			return await orchestratorClient.getForkPointArtifact(slot);
		} catch (error) {
			if (error instanceof OrchestratorApiError && error.code === 'ARTIFACT_NOT_FOUND') {
				return null;
			}
			throw error;
		}
	};

	const bootstrapFromOrchestrator = async () => {
		orchestratorLoadStatus = 'loading';
		orchestratorError = null;

		try {
			const state = await orchestratorClient.getState();
			const forkPointEntries = await Promise.all(
				state.instances.map(
					async (instance) =>
						[instance.slot, await fetchOptionalForkPointArtifact(instance.slot)] as const
				)
			);
			const forkPointsBySlot = new Map(forkPointEntries);

			graphState = bootstrapOrchestratorGraph({
				state: graphState,
				orchestratorState: state,
				forkPointsBySlot
			});

			for (const instance of state.instances) {
				const forkPoint = forkPointsBySlot.get(instance.slot);
				if (!forkPoint) {
					graphState = setForkPointArtifactState(
						graphState,
						instance.slot,
						createMissingArtifactState()
					);
				}
			}

			orchestratorLoadStatus = 'ready';
			ensureSelectedNode();
		} catch (error) {
			orchestratorLoadStatus = 'error';
			orchestratorError =
				error instanceof Error ? error.message : 'Failed to bootstrap orchestrator state.';
		}
	};

	const handleCreateInstance = async () => {
		orchestratorError = null;
		try {
			await orchestratorClient.createInstance();
		} catch (error) {
			orchestratorError = error instanceof Error ? error.message : 'Failed to create instance.';
		}
	};

	const hydrateMergeArtifacts = async (slot: number) => {
		try {
			const [mergeDetails, mergeContext] = await Promise.all([
				orchestratorClient.getMergeDetailsArtifact(slot),
				orchestratorClient.getMergeContextArtifact(slot)
			]);
			graphState = setMergeDetailsArtifactState(
				graphState,
				slot,
				createReadyArtifactState(mergeDetails)
			);
			graphState = setMergeContextArtifactState(
				graphState,
				slot,
				createReadyArtifactState(mergeContext)
			);
		} catch {
			// Merge artifacts are supplementary for now; ignore missing or transient failures.
		}
	};

	const handlePromptSubmit = async () => {
		if (!selectedNode) {
			return;
		}

		const parsedPrompt = safeParse(forkPromptSchema, nodeViewPrompt);
		if (!parsedPrompt.success) {
			return;
		}

		orchestratorError = null;
		try {
			const forkResponse = await orchestratorClient.forkInstance(selectedNode.record.backend.slot);
			graphState = reduceOrchestratorGraphEvent(graphState, {
				type: 'fork_complete',
				...forkResponse
			});

			const nextRecord = graphState.records.find(
				(record) => record.backend.slot === forkResponse.targetSlot
			);
			selectedNodeId = nextRecord?.id ?? selectedNodeId;

			await orchestratorClient.promptInstance(forkResponse.targetSlot, parsedPrompt.output);
			graphState = markNodePromptQueued(graphState, forkResponse.targetSlot);
			nodeViewPrompt = '';
		} catch (error) {
			orchestratorError = error instanceof Error ? error.message : 'Failed to send prompt.';
		}
	};

	const handleMerge = async (sourceNodeId: AgentNodeId, targetNodeId: AgentNodeId) => {
		const sourceSlot = getSlotForNodeId(graphState, sourceNodeId);
		const targetSlot = getSlotForNodeId(graphState, targetNodeId);
		if (sourceSlot === null || targetSlot === null) {
			return;
		}

		orchestratorError = null;
		try {
			await orchestratorClient.merge(sourceSlot, targetSlot);
		} catch (error) {
			orchestratorError = error instanceof Error ? error.message : 'Failed to merge instances.';
		}
	};

	$effect(() => {
		ensureSelectedNode();
	});

	onMount(() => {
		if (!browser) {
			return;
		}

		void bootstrapFromOrchestrator();

		const subscription = subscribeToOrchestratorEvents({
			onEvent: (event) => {
				graphState = reduceOrchestratorGraphEvent(graphState, event);
				if (event.type === 'merge_complete') {
					void hydrateMergeArtifacts(event.integrationSlot);
				}
				ensureSelectedNode();
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
		onSubmit={handlePromptSubmit}
		onCreateInstance={handleCreateInstance}
	/>

	<AgentCanvas
		bind:activeLayoutMode
		{selectedNodeId}
		onSelectedNodeChange={(nodeId) => {
			selectedNodeId = nodeId;
		}}
		onMerge={handleMerge}
		{showNodeDetailsForAll}
		nodes={graph.nodes}
		placements={activePlacements}
		class="h-screen rounded-none border-0"
	/>

	<AgentCanvasSidebar
		bind:activeLayoutMode
		bind:showNodeDetailsForAll
		bind:isOpen={isSidebarOpen}
		{layoutModeOptions}
		orchestratorState={sidebarOrchestratorState}
		{orchestratorLoadStatus}
		{orchestratorStreamStatus}
		{orchestratorError}
		onCreateInstance={handleCreateInstance}
	/>
</div>
