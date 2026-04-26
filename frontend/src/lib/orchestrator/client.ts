import * as v from 'valibot';

import {
	artifactListResponseSchema,
	artifactSchema,
	codeSnapshotSchema,
	contextDiffSchema,
	contextSnapshotSchema,
	eventRecordSchema,
	eventTopics,
	graphSchema,
	healthResponseSchema,
	mergeReportResponseSchema,
	mergeResponseSchema,
	nodeDiffSchema,
	nodeSchema,
	projectSchema,
	runSchema,
	type Artifact,
	type ArtifactId,
	type ArtifactListResponse,
	type CodeSnapshot,
	type CodeSnapshotId,
	type ContextDiff,
	type ContextSnapshot,
	type ContextSnapshotId,
	type EventId,
	type EventRecord,
	type EventTopic,
	type Graph,
	type HealthResponse,
	type MergeReportResponse,
	type MergeResponse,
	type Node,
	type NodeDiff,
	type NodeId,
	type Project,
	type ProjectId,
	type Run,
	type RunId
} from './contracts';

export type FetchLike = typeof globalThis.fetch;

export interface OrchestratorClientOptions {
	baseUrl?: string;
	fetch?: FetchLike;
}

export class OrchestratorApiError extends Error {
	constructor(
		readonly status: number,
		message: string,
		readonly body: unknown
	) {
		super(message);
		this.name = 'OrchestratorApiError';
	}
}

const DEFAULT_BASE_URL = '/api/orchestrator';

export class OrchestratorClient {
	readonly #baseUrl: string;
	readonly #fetch: FetchLike;

	constructor(options: OrchestratorClientOptions = {}) {
		this.#baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '');
		this.#fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
	}

	get baseUrl(): string {
		return this.#baseUrl;
	}

	async health(): Promise<HealthResponse> {
		return this.#get('/health', healthResponseSchema);
	}

	async openProject(path: string): Promise<Project> {
		return this.#post('/projects/open', { path }, projectSchema);
	}

	async getGraph(projectId: ProjectId): Promise<Graph> {
		return this.#get(`/projects/${projectId}/graph`, graphSchema);
	}

	async createRootNode(projectId: ProjectId): Promise<Node> {
		return this.#post(`/projects/${projectId}/nodes/root`, {}, nodeSchema);
	}

	async getNode(projectId: ProjectId, nodeId: NodeId): Promise<Node> {
		return this.#get(`/projects/${projectId}/nodes/${nodeId}`, nodeSchema);
	}

	async getCodeSnapshot(
		projectId: ProjectId,
		snapshotId: CodeSnapshotId
	): Promise<CodeSnapshot> {
		return this.#get(
			`/projects/${projectId}/code-snapshots/${snapshotId}`,
			codeSnapshotSchema
		);
	}

	async getContextSnapshot(
		projectId: ProjectId,
		snapshotId: ContextSnapshotId
	): Promise<ContextSnapshot> {
		return this.#get(
			`/projects/${projectId}/context-snapshots/${snapshotId}`,
			contextSnapshotSchema
		);
	}

	async getNodeDiff(projectId: ProjectId, nodeId: NodeId): Promise<NodeDiff> {
		return this.#get(`/projects/${projectId}/nodes/${nodeId}/diff`, nodeDiffSchema);
	}

	async getNodeContextDiff(projectId: ProjectId, nodeId: NodeId): Promise<ContextDiff> {
		return this.#get(
			`/projects/${projectId}/nodes/${nodeId}/context-diff`,
			contextDiffSchema
		);
	}

	async runMergeResolutionPrompt(
		projectId: ProjectId,
		mergeNodeId: NodeId,
		prompt: string
	): Promise<Run> {
		return this.#post(
			`/projects/${projectId}/merges/${mergeNodeId}/resolution-runs/prompt`,
			{ prompt },
			runSchema
		);
	}

	async listArtifacts(
		projectId: ProjectId,
		options: { nodeId?: NodeId; runId?: RunId } = {}
	): Promise<ArtifactListResponse> {
		const params = new URLSearchParams();
		if (options.nodeId) params.set('node_id', options.nodeId);
		if (options.runId) params.set('run_id', options.runId);
		const suffix = params.toString() ? `?${params.toString()}` : '';
		return this.#get(
			`/projects/${projectId}/artifacts${suffix}`,
			artifactListResponseSchema
		);
	}

	async getArtifact(projectId: ProjectId, artifactId: ArtifactId): Promise<Artifact> {
		return this.#get(
			`/projects/${projectId}/artifacts/${artifactId}`,
			artifactSchema
		);
	}

	artifactContentUrl(projectId: ProjectId, artifactId: ArtifactId): string {
		return this.#url(`/projects/${projectId}/artifacts/${artifactId}/content`);
	}

	/**
	 * URL for downloading the raw bytes of `path` at the given node's
	 * code snapshot. Backend resolves node → snapshot → commit and
	 * `git cat-file blob`s the path. Use as an `<a href>` target —
	 * the daemon sets `Content-Disposition: attachment` so the browser
	 * saves it with the file's basename.
	 */
	nodeFileContentUrl(projectId: ProjectId, nodeId: NodeId, path: string): string {
		const segments = path
			.split('/')
			.map((segment) => encodeURIComponent(segment))
			.join('/');
		return this.#url(`/projects/${projectId}/nodes/${nodeId}/files/${segments}/content`);
	}

	async promptNode(projectId: ProjectId, nodeId: NodeId, prompt: string): Promise<Run> {
		return this.#post(
			`/projects/${projectId}/nodes/${nodeId}/runs/prompt`,
			{ prompt },
			runSchema
		);
	}

	async getRun(projectId: ProjectId, runId: RunId): Promise<Run> {
		return this.#get(`/projects/${projectId}/runs/${runId}`, runSchema);
	}

	async cancelRun(projectId: ProjectId, runId: RunId): Promise<Run> {
		return this.#post(`/projects/${projectId}/runs/${runId}/cancel`, {}, runSchema);
	}

	async mergeNodes(
		projectId: ProjectId,
		sourceNodeId: NodeId,
		targetNodeId: NodeId,
		title?: string
	): Promise<MergeResponse> {
		const body: Record<string, unknown> = {
			source_node_id: sourceNodeId,
			target_node_id: targetNodeId
		};
		if (title !== undefined) {
			body['title'] = title;
		}
		return this.#post(`/projects/${projectId}/merges`, body, mergeResponseSchema);
	}

	async getMergeReport(projectId: ProjectId, nodeId: NodeId): Promise<MergeReportResponse> {
		return this.#get(
			`/projects/${projectId}/merges/${nodeId}/report`,
			mergeReportResponseSchema
		);
	}

	async listEvents(projectId: ProjectId): Promise<readonly EventRecord[]> {
		return this.#get(
			`/projects/${projectId}/events`,
			v.pipe(v.array(eventRecordSchema), v.readonly())
		);
	}

	/**
	 * Subscribe to the project's SSE event stream.
	 * Returns a dispose function that closes the connection.
	 * Requires the browser `EventSource` API — safe only in client code.
	 */
	subscribeEvents(
		projectId: ProjectId,
		handlers: {
			onEvent?: (event: EventRecord) => void;
			onTopic?: (topic: EventTopic, event: EventRecord) => void;
			onError?: (err: Event) => void;
			onOpen?: () => void;
		},
		options: { afterEventId?: EventId } = {}
	): () => void {
		if (typeof EventSource === 'undefined') {
			throw new Error('subscribeEvents requires a browser EventSource');
		}
		// `Last-Event-ID` can't be set on `EventSource` from script — the
		// browser only attaches it on auto-reconnect after a drop. For
		// the manual-reconnect path (e.g. `disconnect()` then
		// `connect()` again) we pass the cursor as `?after_id=` so the
		// daemon can replay missed events from that point.
		const params = new URLSearchParams();
		if (options.afterEventId) params.set('after_id', options.afterEventId);
		const query = params.toString();
		const url = `${this.#baseUrl}/projects/${projectId}/events/stream${
			query ? `?${query}` : ''
		}`;
		const source = new EventSource(url);

		if (handlers.onOpen) {
			source.addEventListener('open', handlers.onOpen);
		}
		if (handlers.onError) {
			source.addEventListener('error', handlers.onError);
		}

		const handleMessage = (message: MessageEvent<string>) => {
			try {
				const parsed = v.parse(eventRecordSchema, JSON.parse(message.data));
				handlers.onEvent?.(parsed);
				handlers.onTopic?.(parsed.topic, parsed);
			} catch (error) {
				console.error('failed to parse orchestrator event', error, message.data);
			}
		};

		// The backend emits named events (event: <topic>\n...). EventSource dispatches
		// these under their name, not 'message'. Register a listener per topic.
		const topicListeners = new Map<string, (ev: MessageEvent<string>) => void>();
		for (const topic of eventTopics) {
			topicListeners.set(topic, handleMessage);
			source.addEventListener(topic, handleMessage);
		}
		// Fallback for unnamed/default messages.
		source.addEventListener('message', handleMessage);

		return () => {
			for (const [topic, listener] of topicListeners) {
				source.removeEventListener(topic, listener);
			}
			source.removeEventListener('message', handleMessage);
			source.close();
		};
	}

	async #get<TSchema extends v.GenericSchema>(
		path: string,
		schema: TSchema
	): Promise<v.InferOutput<TSchema>> {
		const response = await this.#fetch(this.#url(path), {
			method: 'GET',
			headers: { accept: 'application/json' }
		});
		return await this.#parse(response, schema);
	}

	async #post<TSchema extends v.GenericSchema>(
		path: string,
		body: unknown,
		schema: TSchema
	): Promise<v.InferOutput<TSchema>> {
		const response = await this.#fetch(this.#url(path), {
			method: 'POST',
			headers: {
				accept: 'application/json',
				'content-type': 'application/json'
			},
			body: JSON.stringify(body)
		});
		return await this.#parse(response, schema);
	}

	async #parse<TSchema extends v.GenericSchema>(
		response: Response,
		schema: TSchema
	): Promise<v.InferOutput<TSchema>> {
		const rawText = await response.text();
		let parsedBody: unknown = null;
		if (rawText.length > 0) {
			try {
				parsedBody = JSON.parse(rawText);
			} catch {
				parsedBody = rawText;
			}
		}

		if (!response.ok) {
			const detailFromBody =
				parsedBody &&
				typeof parsedBody === 'object' &&
				'detail' in parsedBody &&
				typeof (parsedBody as { detail: unknown }).detail === 'string'
					? (parsedBody as { detail: string }).detail
					: null;
			const detail = detailFromBody ?? response.statusText ?? `HTTP ${response.status}`;
			throw new OrchestratorApiError(response.status, detail, parsedBody);
		}

		return v.parse(schema, parsedBody);
	}

	#url(path: string): string {
		const normalized = path.startsWith('/') ? path : `/${path}`;
		return `${this.#baseUrl}${normalized}`;
	}
}
