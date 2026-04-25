import { SvelteMap } from 'svelte/reactivity';

import type {
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
	getMergedConnectionSegments
} from './layout';
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
	nodes = $state<Node[]>([]);
	selectedNodeId = $state<NodeId | null>(null);
	events = $state<EventRecord[]>([]);
	runsById = new SvelteMap<RunId, Run>();
	mergeResultsByNodeId = new SvelteMap<NodeId, MergeResponse>();
	mergeReportsByNodeId = new SvelteMap<NodeId, MergeReportResponse>();
	codeSnapshotsById = new SvelteMap<CodeSnapshotId, CodeSnapshot>();
	contextSnapshotsById = new SvelteMap<ContextSnapshotId, ContextSnapshot>();
	diffsByNodeId = new SvelteMap<NodeId, NodeDiff>();
	contextDiffsByNodeId = new SvelteMap<NodeId, ContextDiff>();
	connectionStatus = $state<ConnectionStatus>('idle');
	lastError = $state<string | null>(null);
	activeLayoutMode = $state<LayoutMode>('rings');
	recenterKey = $state(0);

	#unsubscribe: (() => void) | null = null;

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
	selectedNode = $derived<Node | null>(
		this.selectedNodeId ? (this.nodes.find((n) => n.id === this.selectedNodeId) ?? null) : null
	);
	rootNodes = $derived<Node[]>(this.nodes.filter((n) => n.parent_node_ids.length === 0));
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
		const graph: Graph = await this.#client.getGraph(projectId);
		this.project = graph.project;
		this.nodes = [...graph.nodes];
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
		return run;
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
		this.#unsubscribe = this.#client.subscribeEvents(this.project.id, {
			onOpen: () => {
				this.connectionStatus = 'open';
			},
			onError: () => {
				this.connectionStatus = 'error';
			},
			onEvent: (event) => {
				this.#handleEvent(event);
			}
		});
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
		this.lastError = null;
		this.connectionStatus = 'idle';
	}

	dispose(): void {
		this.disconnect();
	}

	#handleEvent(event: EventRecord): void {
		this.events = [...this.events, event];
		switch (event.topic) {
			case 'root_node_created':
			case 'prompt_node_created':
			case 'merge_node_created':
			case 'resolution_node_created':
				this.#touchGraphFromEvent();
				break;
			case 'run_created':
			case 'run_started':
			case 'run_succeeded':
			case 'run_failed':
			case 'run_cancelled':
				this.#touchRunFromEvent(event);
				if (event.topic === 'run_succeeded') {
					this.#touchGraphFromEvent();
				}
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
			})
			.catch((error: unknown) => {
				this.lastError = String(error);
			});
	}

	#upsertNode(node: Node): void {
		const idx = this.nodes.findIndex((n) => n.id === node.id);
		if (idx === -1) {
			this.nodes = [...this.nodes, node];
		} else {
			const next = [...this.nodes];
			next[idx] = node;
			this.nodes = next;
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
