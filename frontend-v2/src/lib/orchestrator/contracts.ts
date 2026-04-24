import * as v from 'valibot';

// Field names match the v2 wire format (FastAPI snake_case).

const brandedUuid = <Brand extends string>(brand: Brand) =>
	v.pipe(v.string(), v.uuid(), v.brand(brand));

export const projectIdSchema = brandedUuid('ProjectId');
export type ProjectId = v.InferOutput<typeof projectIdSchema>;

export const nodeIdSchema = brandedUuid('NodeId');
export type NodeId = v.InferOutput<typeof nodeIdSchema>;

export const runIdSchema = brandedUuid('RunId');
export type RunId = v.InferOutput<typeof runIdSchema>;

export const codeSnapshotIdSchema = brandedUuid('CodeSnapshotId');
export type CodeSnapshotId = v.InferOutput<typeof codeSnapshotIdSchema>;

export const contextSnapshotIdSchema = brandedUuid('ContextSnapshotId');
export type ContextSnapshotId = v.InferOutput<typeof contextSnapshotIdSchema>;

export const eventIdSchema = brandedUuid('EventId');
export type EventId = v.InferOutput<typeof eventIdSchema>;

export const nodeKinds = ['root', 'prompt', 'fork', 'merge', 'import', 'manual'] as const;
export type NodeKind = (typeof nodeKinds)[number];
export const nodeKindSchema = v.picklist(nodeKinds);

export const nodeStatuses = [
	'ready',
	'running',
	'failed',
	'cancelled',
	'code_conflicted',
	'context_conflicted',
	'both_conflicted'
] as const;
export type NodeStatus = (typeof nodeStatuses)[number];
export const nodeStatusSchema = v.picklist(nodeStatuses);

export const runStatuses = ['queued', 'running', 'succeeded', 'failed', 'cancelled'] as const;
export type RunStatus = (typeof runStatuses)[number];
export const runStatusSchema = v.picklist(runStatuses);

export const runtimeKinds = [
	'local_subprocess',
	'pi',
	'claude_code',
	'codex',
	'custom'
] as const;
export type RuntimeKind = (typeof runtimeKinds)[number];
export const runtimeKindSchema = v.picklist(runtimeKinds);

export const eventTopics = [
	'project_opened',
	'root_node_created',
	'run_created',
	'run_started',
	'run_succeeded',
	'run_failed',
	'run_cancelled',
	'runtime_event',
	'artifact_created',
	'prompt_node_created',
	'merge_node_created'
] as const;
export type EventTopic = (typeof eventTopics)[number];
export const eventTopicSchema = v.picklist(eventTopics);

// The backend currently emits naive ISO datetimes when SQLite drops the tz on
// read. Accept either form here and let UI helpers normalise to UTC for display.
const isoTimestampSchema = v.pipe(
	v.string(),
	v.regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/, 'Invalid timestamp')
);

export const projectSchema = v.object({
	id: projectIdSchema,
	root_path: v.string(),
	git_dir: v.string(),
	created_at: isoTimestampSchema,
	updated_at: isoTimestampSchema
});
export type Project = v.InferOutput<typeof projectSchema>;

export const nodeSchema = v.object({
	id: nodeIdSchema,
	project_id: projectIdSchema,
	kind: nodeKindSchema,
	parent_node_ids: v.array(nodeIdSchema),
	code_snapshot_id: codeSnapshotIdSchema,
	context_snapshot_id: contextSnapshotIdSchema,
	status: nodeStatusSchema,
	title: v.string(),
	created_at: isoTimestampSchema,
	originating_run_id: v.nullish(runIdSchema)
});
export type Node = v.InferOutput<typeof nodeSchema>;

export const runSchema = v.object({
	id: runIdSchema,
	project_id: projectIdSchema,
	source_node_id: nodeIdSchema,
	prompt: v.string(),
	planned_child_node_id: v.nullish(nodeIdSchema),
	status: runStatusSchema,
	runtime: runtimeKindSchema,
	worktree_path: v.nullish(v.string()),
	transcript_path: v.nullish(v.string()),
	error_message: v.nullish(v.string()),
	started_at: v.nullish(isoTimestampSchema),
	finished_at: v.nullish(isoTimestampSchema)
});
export type Run = v.InferOutput<typeof runSchema>;

export const graphSchema = v.object({
	project: projectSchema,
	nodes: v.array(nodeSchema)
});
export type Graph = v.InferOutput<typeof graphSchema>;

export const eventRecordSchema = v.object({
	id: eventIdSchema,
	project_id: projectIdSchema,
	topic: eventTopicSchema,
	payload: v.record(v.string(), v.unknown()),
	created_at: isoTimestampSchema
});
export type EventRecord = v.InferOutput<typeof eventRecordSchema>;

export const openProjectRequestSchema = v.object({
	path: v.pipe(v.string(), v.minLength(1))
});
export type OpenProjectRequest = v.InferOutput<typeof openProjectRequestSchema>;

export const promptRunRequestSchema = v.object({
	prompt: v.pipe(v.string(), v.minLength(1))
});
export type PromptRunRequest = v.InferOutput<typeof promptRunRequestSchema>;

export const healthResponseSchema = v.object({
	status: v.string(),
	app_name: v.string()
});
export type HealthResponse = v.InferOutput<typeof healthResponseSchema>;

export const mergeNodesRequestSchema = v.object({
	source_node_id: nodeIdSchema,
	target_node_id: nodeIdSchema,
	title: v.nullish(v.pipe(v.string(), v.minLength(1)))
});
export type MergeNodesRequest = v.InferOutput<typeof mergeNodesRequestSchema>;

export const mergeResponseSchema = v.object({
	node: nodeSchema,
	ancestor_node_id: nodeIdSchema,
	code_conflicts: v.array(v.string()),
	context_conflicts: v.array(v.record(v.string(), v.unknown())),
	report_path: v.string()
});
export type MergeResponse = v.InferOutput<typeof mergeResponseSchema>;

export const mergeReportResponseSchema = v.object({
	report: v.record(v.string(), v.unknown())
});
export type MergeReportResponse = v.InferOutput<typeof mergeReportResponseSchema>;

export const codeSnapshotSchema = v.object({
	id: codeSnapshotIdSchema,
	project_id: projectIdSchema,
	commit_sha: v.string(),
	git_ref: v.nullish(v.string()),
	created_at: isoTimestampSchema
});
export type CodeSnapshot = v.InferOutput<typeof codeSnapshotSchema>;

export const contextItemStatuses = ['active', 'resolved', 'superseded', 'conflicted'] as const;
export type ContextItemStatus = (typeof contextItemStatuses)[number];
export const contextItemStatusSchema = v.picklist(contextItemStatuses);

export const contextItemIdSchema = brandedUuid('ContextItemId');
export type ContextItemId = v.InferOutput<typeof contextItemIdSchema>;

export const contextItemSchema = v.object({
	id: contextItemIdSchema,
	text: v.string(),
	status: contextItemStatusSchema,
	provenance_node_id: nodeIdSchema,
	provenance_run_id: v.nullish(runIdSchema),
	citations: v.array(v.string())
});
export type ContextItem = v.InferOutput<typeof contextItemSchema>;

export const fileReferenceSchema = v.object({
	path: v.string()
});
export type FileReference = v.InferOutput<typeof fileReferenceSchema>;

export const symbolReferenceSchema = v.object({
	name: v.string(),
	file_path: v.string(),
	kind: v.string()
});
export type SymbolReference = v.InferOutput<typeof symbolReferenceSchema>;

export const contextSnapshotSchema = v.object({
	id: contextSnapshotIdSchema,
	project_id: projectIdSchema,
	parent_ids: v.array(contextSnapshotIdSchema),
	transcript_ref: v.nullish(v.string()),
	summary: v.string(),
	goals: v.array(contextItemSchema),
	constraints: v.array(contextItemSchema),
	decisions: v.array(contextItemSchema),
	assumptions: v.array(contextItemSchema),
	open_questions: v.array(contextItemSchema),
	todos: v.array(contextItemSchema),
	risks: v.array(contextItemSchema),
	handoff_notes: v.array(contextItemSchema),
	read_files: v.array(fileReferenceSchema),
	touched_files: v.array(fileReferenceSchema),
	symbols: v.array(symbolReferenceSchema),
	merge_metadata: v.nullish(v.record(v.string(), v.unknown())),
	created_at: isoTimestampSchema
});
export type ContextSnapshot = v.InferOutput<typeof contextSnapshotSchema>;

export const diffLineTypes = ['context', 'add', 'remove'] as const;
export type DiffLineType = (typeof diffLineTypes)[number];
export const diffLineTypeSchema = v.picklist(diffLineTypes);

export const diffLineSchema = v.object({
	type: diffLineTypeSchema,
	content: v.string()
});
export type DiffLine = v.InferOutput<typeof diffLineSchema>;

export const diffHunkSchema = v.object({
	header: v.string(),
	old_start: v.number(),
	old_lines: v.number(),
	new_start: v.number(),
	new_lines: v.number(),
	lines: v.array(diffLineSchema)
});
export type DiffHunk = v.InferOutput<typeof diffHunkSchema>;

export const fileChangeTypes = ['modified', 'added', 'deleted', 'renamed'] as const;
export type FileChangeType = (typeof fileChangeTypes)[number];
// Backend may return arbitrary string; we accept then narrow at the UI layer.

export const fileDiffSchema = v.object({
	path: v.string(),
	old_path: v.string(),
	new_path: v.string(),
	change_type: v.string(),
	additions: v.number(),
	deletions: v.number(),
	hunks: v.array(diffHunkSchema)
});
export type FileDiff = v.InferOutput<typeof fileDiffSchema>;

export const diffTotalsSchema = v.object({
	files: v.number(),
	additions: v.number(),
	deletions: v.number()
});
export type DiffTotals = v.InferOutput<typeof diffTotalsSchema>;

export const nodeDiffSchema = v.object({
	node_id: nodeIdSchema,
	base_commit_sha: v.nullish(v.string()),
	head_commit_sha: v.string(),
	totals: diffTotalsSchema,
	files: v.array(fileDiffSchema)
});
export type NodeDiff = v.InferOutput<typeof nodeDiffSchema>;
