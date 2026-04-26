import { SvelteMap } from 'svelte/reactivity';

import type {
	Artifact,
	CodeSnapshot,
	CodeSnapshotId,
	ContextDiff,
	ContextSnapshot,
	ContextSnapshotId,
	EventRecord,
	Graph,
	MergeReportResponse,
	MergeResponse,
	Node,
	NodeDiff,
	NodeId,
	Project,
	ProjectId,
	Run,
	RunId
} from '../orchestrator/contracts';
import { OrchestratorClient } from '../orchestrator/client';

import {
	computeBounds,
	computeLayoutPlacements,
	computeRingLayout,
	getConnectionSegments,
	getMaxNodeDepth,
	getMergedConnectionSegments
} from './layout';
import { isPendingNode, type GraphNode, type PendingNode } from './types';
import type {
	ConnectionSegment,
	LayoutMode,
	MergedConnectionSegment,
	NodePlacement
} from './types';

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'error' | 'closed';

export class GraphStore {
	readonly #client: OrchestratorClient;

	project = $state<Project | null>(null);
	nodes = $state<GraphNode[]>([]);
	selectedNodeId = $state<NodeId | null>(null);
	events = $state<EventRecord[]>([]);
	runsById = new SvelteMap<RunId, Run>();
	mergeResultsByNodeId = new SvelteMap<NodeId, MergeResponse>();
	mergeReportsByNodeId = new SvelteMap<NodeId, MergeReportResponse>();
	codeSnapshotsById = new SvelteMap<CodeSnapshotId, CodeSnapshot>();
	contextSnapshotsById = new SvelteMap<ContextSnapshotId, ContextSnapshot>();
	diffsByNodeId = new SvelteMap<NodeId, NodeDiff>();
	contextDiffsByNodeId = new SvelteMap<NodeId, ContextDiff>();
	artifactsByNodeId = new SvelteMap<NodeId, readonly Artifact[]>();
	pendingNodesById = new SvelteMap<NodeId, PendingNode>();
	connectionStatus = $state<ConnectionStatus>('idle');
	lastError = $state<string | null>(null);
	activeLayoutMode = $state<LayoutMode>('rings');
	// Bumping `recenterKey` signals the canvas to refit instantly — the
	// path the user takes when they click the Recenter button or change
	// layout mode. `smoothRecenterKey` signals an animated tween, used
	// when the canvas auto-frames a newly-reached graph depth so the
	// motion gives a clear "the frame moved" cue without disturbing
	// in-flight gestures.
	recenterKey = $state(0);
	smoothRecenterKey = $state(0);

	#unsubscribe: (() => void) | null = null;
	// Max graph depth (distance from root) we've already framed for. We
	// bump `recenterKey` whenever the max advances so the canvas can
	// smoothly fit the new ring/level into view — without re-fitting on
	// every sibling that lands at an already-known depth.
	#maxDepthSeen = 0;

	#basePlacements = $derived<NodePlacement[]>(computeRingLayout(this.nodes));
	placements = $derived<NodePlacement[]>(
		computeLayoutPlacements({
			nodes: this.nodes,
			basePlacements: this.#basePlacements,
			mode: this.activeLayoutMode
		})
	);
	edges = $derived<ConnectionSegment[]>(getConnectionSegments(this.nodes, this.placements));
	mergedEdges = $derived<MergedConnectionSegment[]>(
		getMergedConnectionSegments(this.nodes, this.placements)
	);
	bounds = $derived(computeBounds(this.placements));
	selectedNode = $derived<GraphNode | null>(
		this.selectedNodeId ? (this.nodes.find((n) => n.id === this.selectedNodeId) ?? null) : null
	);
	rootNodes = $derived<GraphNode[]>(this.nodes.filter((n) => n.parent_node_ids.length === 0));
	runsForSelectedNode = $derived<Run[]>(
		this.selectedNodeId === null
			? []
			: Array.from(this.runsById.values()).filter(
					(r) => r.source_node_id === this.selectedNodeId
				)
	);

	constructor(client: OrchestratorClient = new OrchestratorClient()) {
		this.#client = client;
	}

	get client(): OrchestratorClient {
		return this.#client;
	}

	async openProject(path: string): Promise<Project> {
		this.lastError = null;
		const project = await this.#client.openProject(path);
		this.project = project;
		await this.refreshGraph();
		this.connect();
		return project;
	}

	async refreshGraph(): Promise<void> {
		const projectId = this.#requireProjectId();
		// Re-fetch graph and events together. Events get pulled here too
		// because the SSE stream sometimes silently drops the trailing
		// run events on long pi runs, leaving the inspector tabs empty
		// (which used to fall back to a misleading "mock" placeholder).
		// Manual Refresh is the operator's recovery path; it should hand
		// back the truth, not the partial truth the SSE managed to deliver.
		const [graph, events] = await Promise.all([
			this.#client.getGraph(projectId),
			this.#client.listEvents(projectId)
		]);
		this.project = graph.project;
		this.#mergeAuthoritativeNodes([...graph.nodes]);
		this.events = [...events];
		this.#bumpRecenterIfDepthAdvanced();
	}

	async createRootNode(): Promise<Node> {
		const projectId = this.#requireProjectId();
		const node = await this.#client.createRootNode(projectId);
		this.#upsertNode(node);
		this.selectedNodeId = node.id;
		return node;
	}

	async promptFrom(nodeId: NodeId, prompt: string): Promise<Run> {
		const projectId = this.#requireProjectId();
		const run = await this.#client.promptNode(projectId, nodeId, prompt);
		this.runsById.set(run.id, run);
		this.#upsertPendingNodeFromRun(run, 'prompt', true);
		return run;
	}

	async cancelRun(runId: RunId): Promise<Run> {
		const projectId = this.#requireProjectId();
		const run = await this.#client.cancelRun(projectId, runId);
		this.runsById.set(run.id, run);
		return run;
	}

	async mergeNodes(
		sourceNodeId: NodeId,
		targetNodeId: NodeId,
		title?: string
	): Promise<MergeResponse> {
		const projectId = this.#requireProjectId();
		const result = await this.#client.mergeNodes(projectId, sourceNodeId, targetNodeId, title);
		this.mergeResultsByNodeId.set(result.node.id, result);
		this.#upsertNode(result.node);
		this.selectedNodeId = result.node.id;
		// Eagerly fetch the report so the UI can render conflicts on first paint.
		void this.fetchMergeReport(result.node.id);
		return result;
	}

	async fetchMergeReport(nodeId: NodeId): Promise<MergeReportResponse> {
		const projectId = this.#requireProjectId();
		const report = await this.#client.getMergeReport(projectId, nodeId);
		this.mergeReportsByNodeId.set(nodeId, report);
		return report;
	}

	async fetchCodeSnapshot(snapshotId: CodeSnapshotId): Promise<CodeSnapshot> {
		const cached = this.codeSnapshotsById.get(snapshotId);
		if (cached) return cached;
		const projectId = this.#requireProjectId();
		const snapshot = await this.#client.getCodeSnapshot(projectId, snapshotId);
		this.codeSnapshotsById.set(snapshotId, snapshot);
		return snapshot;
	}

	async fetchContextSnapshot(snapshotId: ContextSnapshotId): Promise<ContextSnapshot> {
		const cached = this.contextSnapshotsById.get(snapshotId);
		if (cached) return cached;
		const projectId = this.#requireProjectId();
		const snapshot = await this.#client.getContextSnapshot(projectId, snapshotId);
		this.contextSnapshotsById.set(snapshotId, snapshot);
		return snapshot;
	}

	async fetchNodeDiff(nodeId: NodeId, options: { force?: boolean } = {}): Promise<NodeDiff> {
		if (!options.force) {
			const cached = this.diffsByNodeId.get(nodeId);
			if (cached) return cached;
		}
		const projectId = this.#requireProjectId();
		const diff = await this.#client.getNodeDiff(projectId, nodeId);
		this.diffsByNodeId.set(nodeId, diff);
		return diff;
	}

	async fetchContextDiff(
		nodeId: NodeId,
		options: { force?: boolean } = {}
	): Promise<ContextDiff> {
		if (!options.force) {
			const cached = this.contextDiffsByNodeId.get(nodeId);
			if (cached) return cached;
		}
		const projectId = this.#requireProjectId();
		const diff = await this.#client.getNodeContextDiff(projectId, nodeId);
		this.contextDiffsByNodeId.set(nodeId, diff);
		return diff;
	}

	async resolveMerge(mergeNodeId: NodeId, prompt: string): Promise<Run> {
		const projectId = this.#requireProjectId();
		const run = await this.#client.runMergeResolutionPrompt(projectId, mergeNodeId, prompt);
		this.runsById.set(run.id, run);
		this.#upsertPendingNodeFromRun(run, 'resolution', true);
		return run;
	}

	async fetchArtifactsForNode(
		nodeId: NodeId,
		options: { force?: boolean } = {}
	): Promise<readonly Artifact[]> {
		if (!options.force) {
			const cached = this.artifactsByNodeId.get(nodeId);
			if (cached) return cached;
		}
		const projectId = this.#requireProjectId();
		const result = await this.#client.listArtifacts(projectId, { nodeId });
		const artifacts = result.artifacts;
		this.artifactsByNodeId.set(nodeId, artifacts);
		return artifacts;
	}

	artifactContentUrl(artifactId: Artifact['id']): string {
		const projectId = this.#requireProjectId();
		return this.#client.artifactContentUrl(projectId, artifactId);
	}

	select(nodeId: NodeId | null): void {
		this.selectedNodeId = nodeId;
	}

	setLayoutMode(mode: LayoutMode): void {
		this.activeLayoutMode = mode;
		this.recenterKey += 1;
	}

	requestRecenter(): void {
		this.recenterKey += 1;
	}

	connect(): void {
		if (!this.project) {
			return;
		}
		this.disconnect();
		this.connectionStatus = 'connecting';
		// On manual (re)connect, hand the daemon the last event id we
		// already saw so it can replay anything that landed during the
		// gap. Browsers handle this automatically for auto-reconnect via
		// `Last-Event-ID`, but a deliberate `disconnect() + connect()`
		// (or an explicit Refresh-driven cycle) starts a fresh
		// EventSource that has no auto-resume cursor.
		const lastEvent = this.events.length > 0 ? this.events[this.events.length - 1] : null;
		this.#unsubscribe = this.#client.subscribeEvents(
			this.project.id,
			{
				onOpen: () => {
					this.connectionStatus = 'open';
				},
				onError: () => {
					this.connectionStatus = 'error';
				},
				onEvent: (event) => {
					this.#handleEvent(event);
				}
			},
			lastEvent ? { afterEventId: lastEvent.id } : {}
		);
	}

	disconnect(): void {
		if (this.#unsubscribe) {
			this.#unsubscribe();
			this.#unsubscribe = null;
		}
		this.connectionStatus = 'closed';
	}

	closeProject(): void {
		this.disconnect();
		this.project = null;
		this.nodes = [];
		this.selectedNodeId = null;
		this.events = [];
		this.runsById.clear();
		this.mergeResultsByNodeId.clear();
		this.mergeReportsByNodeId.clear();
		this.codeSnapshotsById.clear();
		this.contextSnapshotsById.clear();
		this.diffsByNodeId.clear();
		this.contextDiffsByNodeId.clear();
		this.artifactsByNodeId.clear();
		this.pendingNodesById.clear();
		this.lastError = null;
		this.connectionStatus = 'idle';
		this.#maxDepthSeen = 0;
	}

	dispose(): void {
		this.disconnect();
	}

	#handleEvent(event: EventRecord): void {
		// Dedupe by id. Live SSE delivery and the Refresh-poll's
		// `listEvents` round-trip can both deliver the same event:
		// Refresh resets `this.events` to the full API list, and
		// shortly after, an in-flight SSE frame for an event already
		// in that list arrives via `#handleEvent`. Without this guard
		// keyed `{#each events as event (event.id)}` blocks (notably
		// `TerminalOutput`) hit `each_key_duplicate` and Svelte 5
		// throws mid-render, breaking downstream reactivity.
		if (this.events.some((existing) => existing.id === event.id)) return;
		this.events = [...this.events, event];
		switch (event.topic) {
			case 'root_node_created':
			case 'prompt_node_created':
			case 'merge_node_created':
			case 'resolution_node_created':
				this.#touchGraphFromEvent();
				break;
			case 'run_created':
				this.#touchPendingNodeFromRunCreatedEvent(event);
				this.#touchRunFromEvent(event);
				break;
			case 'run_started':
			case 'run_failed':
			case 'run_cancelled':
				this.#touchRunFromEvent(event);
				this.#touchPendingNodeStatusFromEvent(event);
				break;
			case 'run_succeeded':
				this.#touchRunFromEvent(event);
				this.#touchGraphFromEvent();
				break;
			case 'runtime_event':
			case 'artifact_created':
			case 'project_opened':
				// No graph/run change implied.
				break;
		}
	}

	#touchGraphFromEvent(): void {
		// Server payload shapes evolve; refreshing the graph is authoritative.
		void this.refreshGraph().catch((error: unknown) => {
			this.lastError = String(error);
		});
	}

	#touchRunFromEvent(event: EventRecord): void {
		const runId = extractRunId(event);
		if (!runId || !this.project) {
			return;
		}
		void this.#client
			.getRun(this.project.id, runId)
			.then((run) => {
				this.runsById.set(run.id, run);
				this.#syncPendingNodeStatus(run);
			})
			.catch((error: unknown) => {
				this.lastError = String(error);
			});
	}

	#touchPendingNodeFromRunCreatedEvent(event: EventRecord): void {
		const runId = extractRunId(event);
		const childId = extractNodeId(event.payload['planned_child_node_id']);
		const sourceNodeId = extractNodeId(event.payload['source_node_id']);
		if (!runId || !childId || !sourceNodeId || !this.project) return;
		const sourceNode = this.nodes.find((node) => node.id === sourceNodeId);
		if (!sourceNode) return;
		const prompt = typeof event.payload['prompt'] === 'string' ? event.payload['prompt'] : '';
		const existingRun = this.runsById.get(runId);
		const run: Run = existingRun ?? {
			id: runId,
			project_id: this.project.id,
			source_node_id: sourceNodeId,
			prompt,
			planned_child_node_id: childId,
			status: 'running',
			runtime: event.payload['runtime'] === 'pi' ? 'pi' : 'noop',
			sandbox: event.payload['sandbox'] === 'docker' || event.payload['sandbox'] === 'bubblewrap'
				? event.payload['sandbox']
				: 'none',
			worktree_path: null,
			transcript_path: null,
			error_message: null,
			started_at: null,
			finished_at: null
		};
		this.#upsertPendingNodeFromRun(run, sourceNode.kind === 'merge' ? 'resolution' : 'prompt', false);
	}

	#touchPendingNodeStatusFromEvent(event: EventRecord): void {
		const runId = extractRunId(event);
		if (!runId) return;
		const run = this.runsById.get(runId);
		if (run) {
			this.#syncPendingNodeStatus(run);
		}
	}

	#syncPendingNodeStatus(run: Run): void {
		if (!run.planned_child_node_id) return;
		const pending = this.pendingNodesById.get(run.planned_child_node_id);
		if (!pending) return;
		const status = run.status === 'failed' || run.status === 'cancelled' ? run.status : 'running';
		this.pendingNodesById.set(pending.id, { ...pending, status });
		this.#rebuildNodesKeepingPending();
	}

	#upsertPendingNodeFromRun(run: Run, kind: PendingNode['kind'], select: boolean): void {
		if (!run.planned_child_node_id) return;
		if (this.nodes.some((node) => !isPendingNode(node) && node.id === run.planned_child_node_id)) {
			if (select) this.selectedNodeId = run.planned_child_node_id;
			return;
		}
		const existing = this.pendingNodesById.get(run.planned_child_node_id);
		const parentNode = this.nodes.find((node) => node.id === run.source_node_id);
		const pending: PendingNode = {
			pending: true,
			id: run.planned_child_node_id,
			project_id: run.project_id,
			kind,
			parent_node_ids: [run.source_node_id],
			status: run.status === 'failed' || run.status === 'cancelled' ? run.status : 'running',
			title: promptTitle(run.prompt),
			created_at: existing?.created_at ?? run.started_at ?? new Date().toISOString(),
			originating_run_id: run.id
		};
		if (!parentNode && !existing) return;
		this.pendingNodesById.set(pending.id, pending);
		this.#rebuildNodesKeepingPending();
		if (select) {
			this.selectedNodeId = pending.id;
		}
	}

	#mergeAuthoritativeNodes(nodes: Node[]): void {
		const authoritativeIds = new Set(nodes.map((node) => node.id));
		for (const id of this.pendingNodesById.keys()) {
			if (authoritativeIds.has(id)) {
				this.pendingNodesById.delete(id);
			}
		}
		this.nodes = [...nodes, ...this.pendingNodesById.values()];
	}

	#rebuildNodesKeepingPending(): void {
		const durableNodes = this.nodes.filter((node): node is Node => !isPendingNode(node));
		this.#mergeAuthoritativeNodes(durableNodes);
		this.#bumpRecenterIfDepthAdvanced();
	}

	#upsertNode(node: Node): void {
		this.pendingNodesById.delete(node.id);
		const idx = this.nodes.findIndex((n) => n.id === node.id);
		if (idx === -1) {
			this.nodes = [...this.nodes, node];
		} else {
			const next = [...this.nodes];
			next[idx] = node;
			this.nodes = next;
		}
		this.#bumpRecenterIfDepthAdvanced();
	}

	#bumpRecenterIfDepthAdvanced(): void {
		const currentMax = getMaxNodeDepth(this.nodes);
		if (currentMax > this.#maxDepthSeen) {
			this.#maxDepthSeen = currentMax;
			this.smoothRecenterKey += 1;
		}
	}

	#requireProjectId(): ProjectId {
		if (!this.project) {
			throw new Error('Project is not open');
		}
		return this.project.id;
	}
}

function extractRunId(event: EventRecord): RunId | null {
	const candidate = event.payload['run_id'];
	return typeof candidate === 'string' ? (candidate as RunId) : null;
}

function extractNodeId(value: unknown): NodeId | null {
	return typeof value === 'string' ? (value as NodeId) : null;
}

function promptTitle(prompt: string): string {
	const singleLine = prompt.replace(/\s+/g, ' ').trim();
	return singleLine.length > 48 ? `${singleLine.slice(0, 47)}…` : singleLine || 'Running prompt';
}
