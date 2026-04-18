<script lang="ts">
	import { onMount, tick } from 'svelte';

	import AgentCanvas from '$lib/components/agent-graph/AgentCanvas.svelte';
	import AgentCanvasSidebar from '$lib/components/agent-graph/AgentCanvasSidebar.svelte';
	import type { ControlOption } from '$lib/components/primitives/types';
	import { computeLayoutPlacements } from '$lib/agent-graph/layout';
	import {
		createEmptyLineageState,
		applyOrchestratorEvent,
		agentNodeIdToSlot,
		buildAgentNodes,
		buildBasePlacements,
		getResolvedForkPoint,
		slotToAgentNodeId,
		type AgentExecutionState,
		type ExplainMode,
		type OrchestratorState
	} from '$lib/orchestrator/contracts';
	import {
		connectToOrchestratorEvents,
		createRootInstance,
		fetchOrchestratorState,
		forkInstance,
		mergeInstances,
		promptInstance,
		stopInstance
	} from '$lib/orchestrator/client';
	import { layoutModes, type AgentNodeId, type LayoutMode } from '$lib/agent-graph/types';

	type ConnectionStatus = 'connecting' | 'open' | 'error';

	const refreshEventTypes = new Set([
		'instance_created',
		'instance_stopped',
		'fork_complete',
		'merge_integration_created',
		'merge_complete',
		'fork_point_recorded',
		'git_status'
	]);

	const layoutModeOptions: readonly ControlOption[] = layoutModes.map((mode) => ({
		value: mode,
		label: mode === 'rings' ? 'Concentric rings' : mode === 'tree' ? 'Tree' : 'Force'
	}));

	let orchestratorState = $state<OrchestratorState | null>(null);
	let lineage = $state(createEmptyLineageState());
	let executionBySlot = $state<Record<number, AgentExecutionState>>({});
	let terminalBySlot = $state<Record<number, string>>({});
	let activeLayoutMode = $state<LayoutMode>('rings');
	let showNodeDetailsForAll = $state(true);
	let selectedNodeId = $state<AgentNodeId | null>(null);
	let nodeViewPrompt = $state('');
	let isSidebarOpen = $state(true);
	let explainMode = $state<ExplainMode>('direct');
	let connectionStatus = $state<ConnectionStatus>('connecting');
	let pageError = $state<string | null>(null);
	let actionInFlight = $state<string | null>(null);
	let pendingSelectedSlot = $state<number | null>(null);
	let terminalViewport = $state<HTMLDivElement | null>(null);
	let refreshInFlight = false;
	let refreshQueued = false;

	const instances = $derived(orchestratorState?.instances ?? []);
	const nodes = $derived(buildAgentNodes(instances, lineage, executionBySlot, terminalBySlot));
	const basePlacements = $derived(buildBasePlacements(instances));
	const activePlacements = $derived(
		computeLayoutPlacements({
			nodes,
			basePlacements,
			mode: activeLayoutMode
		})
	);
	const selectedNode = $derived(nodes.find((node) => node.id === selectedNodeId) ?? null);
	const selectedSlot = $derived(selectedNodeId ? agentNodeIdToSlot(selectedNodeId) : null);
	const selectedInstance = $derived(
		selectedSlot === null ? null : instances.find((instance) => instance.slot === selectedSlot) ?? null
	);
	const selectedLineage = $derived(
		selectedInstance ? (lineage.bySlot[selectedInstance.slot] ?? null) : null
	);
	const selectedForkPoint = $derived(
		selectedInstance ? getResolvedForkPoint(selectedInstance, lineage) : null
	);
	const selectedTerminalText = $derived(
		selectedSlot === null ? '' : (terminalBySlot[selectedSlot] ?? '')
	);
	const selectedChangedFileCount = $derived(selectedForkPoint?.git?.changedFiles?.length ?? 0);
	const selectedMergedLabels = $derived(
		(selectedLineage?.mergedSourceSlots ?? [])
			.map((slot) => instances.find((instance) => instance.slot === slot)?.label ?? `pi-${slot + 1}`)
			.join(', ')
	);
	const canSubmitPrompt = $derived(
		selectedInstance !== null && nodeViewPrompt.trim().length > 0 && actionInFlight === null
	);
	const canCreateRoot = $derived(instances.length === 0 && actionInFlight === null);

	$effect(() => {
		if (pendingSelectedSlot !== null) {
			const pendingNodeId = slotToAgentNodeId(pendingSelectedSlot);
			if (nodes.some((node) => node.id === pendingNodeId)) {
				selectedNodeId = pendingNodeId;
				pendingSelectedSlot = null;
				return;
			}
		}

		if (selectedNodeId && nodes.some((node) => node.id === selectedNodeId)) {
			return;
		}

		selectedNodeId = nodes[0]?.id ?? null;
	});

	$effect(() => {
		selectedTerminalText;
		void tick().then(() => {
			if (!terminalViewport) return;
			terminalViewport.scrollTop = terminalViewport.scrollHeight;
		});
	});

	function appendTerminal(slot: number, text: string) {
		const nextText = `${terminalBySlot[slot] ?? ''}${text}`.slice(-24_000);
		terminalBySlot = {
			...terminalBySlot,
			[slot]: nextText
		};
	}

	async function refreshState() {
		if (refreshInFlight) {
			refreshQueued = true;
			return;
		}

		refreshInFlight = true;
		try {
			const nextState = await fetchOrchestratorState();
			orchestratorState = nextState;
			const liveSlots = new Set(nextState.instances.map((instance) => instance.slot));
			executionBySlot = Object.fromEntries(
				Object.entries(executionBySlot).filter(([slot]) => liveSlots.has(Number(slot)))
			);
			terminalBySlot = Object.fromEntries(
				Object.entries(terminalBySlot).filter(([slot]) => liveSlots.has(Number(slot)))
			);
			pageError = null;
		} catch (error) {
			pageError = error instanceof Error ? error.message : 'Failed to load orchestrator state.';
			connectionStatus = 'error';
		} finally {
			refreshInFlight = false;
			if (refreshQueued) {
				refreshQueued = false;
				void refreshState();
			}
		}
	}

	function handleEvent(event: Record<string, unknown>) {
		lineage = applyOrchestratorEvent(lineage, event);

		const slot = typeof event.slot === 'number' ? event.slot : null;
		if (slot !== null && event.type === 'session_output' && typeof event.text === 'string') {
			appendTerminal(slot, event.text);
		}

		if (
			slot !== null &&
			event.type === 'pi_event' &&
			typeof event.event === 'object' &&
			event.event !== null
		) {
			const eventType = Reflect.get(event.event, 'type');
			if (eventType === 'agent_start') {
				executionBySlot = { ...executionBySlot, [slot]: 'running' };
			} else if (eventType === 'agent_end') {
				executionBySlot = { ...executionBySlot, [slot]: 'completed' };
			}
		}

		if (refreshEventTypes.has(String(event.type))) {
			void refreshState();
		}
	}

	async function runAction(actionLabel: string, operation: () => Promise<void>) {
		pageError = null;
		actionInFlight = actionLabel;
		try {
			await operation();
		} catch (error) {
			pageError = error instanceof Error ? error.message : `Failed to ${actionLabel}.`;
		} finally {
			actionInFlight = null;
		}
	}

	async function handleCreateRoot() {
		await runAction('create root', async () => {
			const created = await createRootInstance();
			pendingSelectedSlot = created.slot;
			await refreshState();
		});
	}

	async function handlePromptSubmit() {
		const slot = selectedSlot;
		const message = nodeViewPrompt.trim();
		if (slot === null || message.length === 0) {
			return;
		}

		nodeViewPrompt = '';
		executionBySlot = { ...executionBySlot, [slot]: 'running' };
		await runAction('send prompt', async () => {
			await promptInstance(slot, message);
		});
	}

	async function handleForkSelected() {
		if (selectedSlot === null) {
			return;
		}

		await runAction('fork node', async () => {
			const result = await forkInstance(selectedSlot);
			pendingSelectedSlot = result.targetSlot;
			await refreshState();
		});
	}

	async function handleStopSelected() {
		if (selectedSlot === null) {
			return;
		}

		const stoppingSlot = selectedSlot;
		await runAction('stop node', async () => {
			await stopInstance(stoppingSlot);
			await refreshState();
		});
	}

	async function handleMerge(sourceNodeId: AgentNodeId, targetNodeId: AgentNodeId) {
		const sourceSlot = agentNodeIdToSlot(sourceNodeId);
		const targetSlot = agentNodeIdToSlot(targetNodeId);
		if (sourceSlot === targetSlot) {
			return;
		}

		await runAction('merge branches', async () => {
			const result = await mergeInstances(sourceSlot, targetSlot);
			pendingSelectedSlot = result.integrationSlot;
			await refreshState();
		});
	}

	onMount(() => {
		void refreshState();
		const source = connectToOrchestratorEvents(handleEvent);
		source.onopen = () => {
			connectionStatus = 'open';
		};
		source.onerror = () => {
			connectionStatus = 'error';
		};
		return () => source.close();
	});

	function formatTimestamp(timestamp: number | null | undefined) {
		if (!timestamp) return 'Unknown';
		return new Date(timestamp).toLocaleString();
	}
</script>

<svelte:head>
	<title>Agents of Chaos</title>
	<meta
		name="description"
		content="Live graph UI for orchestrated coding-agent branches, forks, and integration merges."
	/>
</svelte:head>

<div class="canvas-page frontend-integration-page">
	<aside class="node-inspector" aria-label="Selected node inspector">
		<div class="node-inspector__header">
			<div>
				<p class="node-inspector__eyebrow">Orchestrator graph</p>
				{#if selectedInstance}
					<h1 class="node-inspector__title">{selectedInstance.label}</h1>
					<p class="node-inspector__status">
						Node {selectedInstance.slot + 1} · {selectedNode?.status ?? 'completed'}
					</p>
				{:else}
					<h1 class="node-inspector__title">No live nodes yet</h1>
					<p class="node-inspector__status">
						Create a root instance to start the graph, then fork and merge directly from the canvas.
					</p>
				{/if}
			</div>
			<div class="node-inspector__header-actions">
				{#if actionInFlight}
					<span class="node-inspector__busy">{actionInFlight}…</span>
				{/if}
			</div>
		</div>

		{#if pageError}
			<section class="node-inspector__error" role="alert">{pageError}</section>
		{/if}

		{#if selectedInstance}
			<section class="node-inspector__meta-grid">
				<div class="node-inspector__meta-card">
					<span class="node-inspector__meta-label">Agent UUID</span>
					<code>{selectedInstance.agentUuid}</code>
				</div>
				<div class="node-inspector__meta-card">
					<span class="node-inspector__meta-label">Git</span>
					<p>{selectedForkPoint?.git?.shortHead ?? 'No fork point yet'}</p>
				</div>
				<div class="node-inspector__meta-card">
					<span class="node-inspector__meta-label">Changed files</span>
					<p>{selectedChangedFileCount}</p>
				</div>
				<div class="node-inspector__meta-card">
					<span class="node-inspector__meta-label">Captured</span>
					<p>{formatTimestamp(selectedForkPoint?.capturedAt)}</p>
				</div>
			</section>

			<section class="node-inspector__lineage-card">
				<div>
					<p class="node-inspector__meta-label">Lineage</p>
					<p>
						{selectedLineage?.parentSlot !== null && selectedLineage?.parentSlot !== undefined
							? `Forked from pi-${selectedLineage.parentSlot + 1}`
							: 'Root instance'}
					</p>
					{#if selectedMergedLabels}
						<p class="node-inspector__meta-subcopy">Merged from {selectedMergedLabels}</p>
					{/if}
				</div>
				{#if selectedForkPoint?.git?.shortStat}
					<p class="node-inspector__meta-subcopy">{selectedForkPoint.git.shortStat}</p>
				{/if}
			</section>

			<section class="node-inspector__actions">
				<button type="button" class="node-inspector__button" onclick={handleForkSelected}>
					Fork
				</button>
				<button
					type="button"
					class="node-inspector__button node-inspector__button--danger"
					onclick={handleStopSelected}
				>
					Stop
				</button>
			</section>

			<section class="node-inspector__composer">
				<label class="node-inspector__meta-label" for="node-view-prompt">Prompt</label>
				<textarea
					id="node-view-prompt"
					class="node-inspector__textarea"
					bind:value={nodeViewPrompt}
					rows="4"
					placeholder="Continue from this node…"
					onkeydown={(event) => {
						if (event.key === 'Enter' && !event.shiftKey) {
							event.preventDefault();
							void handlePromptSubmit();
						}
					}}
				></textarea>
				<div class="node-inspector__composer-actions">
					<button
						type="button"
						class="node-inspector__button node-inspector__button--primary"
						disabled={!canSubmitPrompt}
						onclick={handlePromptSubmit}
					>
						Send
					</button>
				</div>
			</section>

			<section class="node-inspector__terminal-wrap">
				<div class="node-inspector__terminal-header">
					<h2>Live output</h2>
					<span>{connectionStatus}</span>
				</div>
				<div bind:this={terminalViewport} class="node-inspector__terminal-viewport">
					<pre class="node-inspector__terminal">{selectedTerminalText || '> waiting for orchestrator output…'}</pre>
				</div>
			</section>
		{:else}
			<section class="node-inspector__empty-panel">
				<p>
					The graph starts empty. Use <strong>New root</strong> to create the first live pi instance, then
					click nodes, drag from one node to another to merge, and inspect fork-point summaries here.
				</p>
				<div class="node-inspector__actions">
					<button
						type="button"
						class="node-inspector__button node-inspector__button--primary"
						onclick={handleCreateRoot}
					>
						Create root instance
					</button>
				</div>
			</section>
		{/if}
	</aside>

	<AgentCanvas
		bind:activeLayoutMode
		{selectedNodeId}
		onSelectedNodeChange={(nodeId) => {
			selectedNodeId = nodeId;
		}}
		onMerge={(sourceNodeId, targetNodeId) => {
			void handleMerge(sourceNodeId, targetNodeId);
		}}
		{showNodeDetailsForAll}
		{nodes}
		placements={activePlacements}
		class="frontend-integration-page__canvas"
	/>

	<AgentCanvasSidebar
		bind:activeLayoutMode
		bind:showNodeDetailsForAll
		bind:isOpen={isSidebarOpen}
		bind:explainMode
		connectionStatus={connectionStatus}
		instanceCount={instances.length}
		onCreateRoot={() => {
			void handleCreateRoot();
		}}
		onRefresh={() => {
			void refreshState();
		}}
		isCreateDisabled={!canCreateRoot}
		isRefreshDisabled={actionInFlight !== null}
		{layoutModeOptions}
	/>
</div>

<style>
	:global(.frontend-integration-page__canvas) {
		height: 100vh;
		border: 0;
		border-radius: 0;
	}

	.node-inspector {
		position: absolute;
		top: 1rem;
		left: 1rem;
		bottom: 1rem;
		z-index: 20;
		width: min(42rem, 46vw);
		display: grid;
		grid-template-rows: auto auto auto auto auto minmax(0, 1fr);
		gap: 0.9rem;
		padding: 1.1rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 1.6rem;
		background: rgb(18 19 15 / 0.9);
		backdrop-filter: blur(18px);
		box-shadow: var(--shadow-panel);
	}

	.node-inspector__header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}

	.node-inspector__header-actions {
		display: flex;
		align-items: flex-start;
		justify-content: flex-end;
		gap: 0.6rem;
		flex-wrap: wrap;
	}

	.node-inspector__eyebrow,
	.node-inspector__meta-label {
		font-size: 0.68rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}

	.node-inspector__title {
		margin-top: 0.35rem;
		font-size: 1.2rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.node-inspector__status,
	.node-inspector__meta-subcopy {
		margin-top: 0.25rem;
		font-size: 0.76rem;
		line-height: 1.45;
		color: color-mix(in srgb, var(--color-primary) 42%, var(--color-text));
	}

	.node-inspector__busy {
		align-self: flex-start;
		border: 1px solid color-mix(in srgb, var(--color-primary) 34%, transparent);
		border-radius: 999px;
		padding: 0.45rem 0.7rem;
		font-size: 0.7rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--color-primary);
	}

	.node-inspector__error,
	.node-inspector__empty-panel,
	.node-inspector__lineage-card,
	.node-inspector__meta-card,
	.node-inspector__composer,
	.node-inspector__terminal-wrap {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 1.1rem;
		background: rgb(12 13 10 / 0.72);
	}

	.node-inspector__error {
		padding: 0.8rem 1rem;
		color: var(--color-danger);
		font-size: 0.85rem;
	}

	.node-inspector__meta-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.8rem;
	}

	.node-inspector__meta-card,
	.node-inspector__lineage-card {
		padding: 0.85rem 1rem;
	}

	.node-inspector__meta-card code,
	.node-inspector__meta-card p,
	.node-inspector__lineage-card p {
		margin-top: 0.28rem;
		font-size: 0.82rem;
		line-height: 1.45;
		color: var(--color-text);
		word-break: break-word;
	}

	.node-inspector__actions,
	.node-inspector__composer-actions {
		display: flex;
		gap: 0.6rem;
		justify-content: flex-end;
	}

	.node-inspector__button {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 88%, black);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.7rem 1rem;
		font-size: 0.72rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
		transition:
			transform 180ms ease,
			border-color 180ms ease,
			opacity 180ms ease;
	}

	.node-inspector__button:hover:not(:disabled) {
		transform: translateY(-1px);
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
	}

	.node-inspector__button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.node-inspector__button--primary {
		border-color: color-mix(in srgb, var(--color-primary) 52%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 22%, rgb(18 19 15 / 1));
	}

	.node-inspector__button--danger {
		color: var(--color-danger);
	}

	.node-inspector__composer {
		display: grid;
		gap: 0.45rem;
		padding: 0.85rem 1rem;
	}

	.node-inspector__textarea {
		width: 100%;
		resize: vertical;
		min-height: 6rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 84%, transparent);
		border-radius: 1rem;
		background: rgb(11 12 10 / 0.92);
		padding: 0.9rem 1rem;
		font: inherit;
		color: var(--color-text);
	}

	.node-inspector__textarea:focus {
		outline: 1px solid color-mix(in srgb, var(--color-primary) 52%, transparent);
		outline-offset: 0;
	}

	.node-inspector__terminal-wrap {
		min-height: 0;
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		overflow: hidden;
	}

	.node-inspector__terminal-viewport {
		min-height: 0;
		overflow: auto;
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
	}

	.node-inspector__terminal-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.8rem 1rem 0;
		font-size: 0.72rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}

	.node-inspector__terminal {
		margin: 0;
		padding: 1.1rem 1rem 1.2rem;
		min-height: 100%;
		box-sizing: border-box;
		font-family:
			'Berkeley Mono', 'JetBrains Mono', 'SFMono-Regular', Menlo, Monaco, Consolas, monospace;
		font-size: 0.94rem;
		line-height: 1.72;
		color: #cfd7bc;
		white-space: pre-wrap;
	}

	.node-inspector__empty-panel {
		padding: 1rem;
		font-size: 0.88rem;
		line-height: 1.6;
		color: var(--color-text-muted);
	}

	@media (max-width: 1200px) {
		.node-inspector {
			width: min(34rem, calc(100vw - 5.5rem));
		}
	}

	@media (max-width: 900px) {
		.node-inspector {
			width: min(30rem, calc(100vw - 5.5rem));
			grid-template-rows: repeat(5, auto) minmax(24rem, 1.8fr);
		}
	}

	@media (max-width: 640px) {
		.node-inspector {
			top: 0.75rem;
			left: 0.75rem;
			right: 4.25rem;
			bottom: 0.75rem;
			width: auto;
		}

		.node-inspector__meta-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
