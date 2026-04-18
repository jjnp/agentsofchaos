import * as v from 'valibot';

const nullableStringSchema = v.nullable(v.string());
const slotSchema = v.pipe(v.number(), v.integer(), v.minValue(0));

export const orchestratorInstanceStatuses = ['running', 'stopped'] as const;
export type OrchestratorInstanceStatus = (typeof orchestratorInstanceStatuses)[number];

export const orchestratorInstanceStatusSchema = v.picklist(orchestratorInstanceStatuses);

export const forkPointContextUsageSchema = v.object({
	assistantMessages: v.pipe(v.number(), v.integer(), v.minValue(0)),
	totalEntries: v.pipe(v.number(), v.integer(), v.minValue(0)),
	inputTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
	outputTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
	cacheReadTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
	cacheWriteTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
	totalTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
	latestResponseTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
	latestStopReason: v.nullable(v.string())
});

export const forkPointGitSchema = v.object({
	head: v.nullable(v.string()),
	shortHead: v.nullable(v.string()),
	status: v.nullable(v.string()),
	subject: v.nullable(v.string()),
	parents: v.nullable(v.string()),
	shortStat: v.nullable(v.string()),
	changedFiles: v.array(v.string()),
	numStat: v.array(v.string()),
	patch: v.string()
});

export const forkPointSummarySchema = v.object({
	format: v.string(),
	markdown: v.string(),
	preview: v.nullable(v.string()),
	readFiles: v.array(v.string()),
	modifiedFiles: v.array(v.string())
});

export const forkPointSessionSchema = v.object({
	path: v.nullable(v.string()),
	latestEntryId: v.nullable(v.string()),
	totalEntries: v.pipe(v.number(), v.integer(), v.minValue(0)),
	assistantMessages: v.pipe(v.number(), v.integer(), v.minValue(0)),
	latestStopReason: v.nullable(v.string())
});

export const forkPointArtifactSchema = v.object({
	reason: v.string(),
	capturedAt: v.pipe(v.number(), v.integer(), v.minValue(0)),
	slot: slotSchema,
	label: v.string(),
	agentUuid: v.string(),
	git: forkPointGitSchema,
	session: forkPointSessionSchema,
	contextUsage: forkPointContextUsageSchema,
	summary: forkPointSummarySchema,
	mergeSourceSlot: v.optional(slotSchema),
	mergeTargetSlot: v.optional(slotSchema)
});

export const forkPointEventSummarySchema = v.object({
	reason: v.string(),
	capturedAt: v.pipe(v.number(), v.integer(), v.minValue(0)),
	git: v.object({
		shortHead: v.nullable(v.string()),
		shortStat: v.nullable(v.string()),
		changedFiles: v.array(v.string())
	}),
	contextUsage: v.object({
		totalTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
		latestResponseTokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
		assistantMessages: v.pipe(v.number(), v.integer(), v.minValue(0))
	}),
	summary: v.object({
		format: v.string(),
		preview: v.nullable(v.string()),
		readFiles: v.array(v.string()),
		modifiedFiles: v.array(v.string())
	})
});

export const mergeDetailsSchema = v.object({
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	integrationSlot: slotSchema,
	remoteName: v.string(),
	mergeExitCode: v.number(),
	sourceSessionPath: nullableStringSchema,
	targetSessionPath: nullableStringSchema,
	mergeStdout: v.string(),
	mergeStderr: v.string()
});

export const orchestratorInstanceSchema = v.object({
	slot: slotSchema,
	label: v.string(),
	agentUuid: v.string(),
	containerName: nullableStringSchema,
	sessionId: nullableStringSchema,
	sourceImage: v.string(),
	status: orchestratorInstanceStatusSchema,
	lastGitStatus: nullableStringSchema,
	lastForkPoint: v.nullable(forkPointArtifactSchema)
});

export const orchestratorStateSchema = v.object({
	sessionId: v.string(),
	model: v.string(),
	mergeModel: v.string(),
	instanceCount: v.pipe(v.number(), v.integer(), v.minValue(0)),
	instances: v.array(orchestratorInstanceSchema)
});

export const orchestratorInstancesResponseSchema = v.object({
	instances: v.array(orchestratorInstanceSchema)
});

export const createInstanceResponseSchema = v.object({
	slot: slotSchema,
	label: v.string(),
	agentUuid: v.string()
});

export const promptInstanceResponseSchema = v.object({
	accepted: v.boolean(),
	slot: slotSchema,
	queuedAt: v.pipe(v.number(), v.integer(), v.minValue(0))
});

export const forkInstanceResponseSchema = v.object({
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	targetLabel: v.string(),
	image: v.string(),
	forkPoint: forkPointArtifactSchema
});

export const mergePrepResponseSchema = v.object({
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	remoteName: v.string(),
	bytes: v.pipe(v.number(), v.integer(), v.minValue(0)),
	nextStep: v.string()
});

export const mergeResponseSchema = v.object({
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	integrationSlot: slotSchema,
	remoteName: v.string(),
	mergeExitCode: v.number(),
	mergeContextPath: v.string()
});

export const stopInstanceResponseSchema = v.object({
	ok: v.boolean(),
	slot: slotSchema,
	label: v.string(),
	agentUuid: v.string()
});

export const apiErrorSchema = v.object({
	error: v.object({
		code: v.string(),
		message: v.string()
	})
});

const eventBaseSchema = {
	type: v.string()
} as const;

export const gridBootEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('grid_boot'),
	session: v.string(),
	gridSize: v.pipe(v.number(), v.integer(), v.minValue(0)),
	model: v.string(),
	mergeModel: v.string()
});

export const gridReadyEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('grid_ready'),
	session: v.string(),
	gridSize: v.pipe(v.number(), v.integer(), v.minValue(0)),
	model: v.string()
});

export const instanceCreatedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('instance_created'),
	slot: slotSchema,
	label: v.string(),
	agentUuid: v.string()
});

export const instanceStoppedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('instance_stopped'),
	slot: slotSchema,
	label: v.string(),
	agentUuid: v.string()
});

export const sessionReadyEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('session_ready'),
	slot: slotSchema,
	label: v.string(),
	sessionId: v.string(),
	model: v.string(),
	workspace: v.string(),
	agentDir: v.string(),
	agentUuid: v.string(),
	containerName: v.optional(v.string())
});

export const sessionOutputEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('session_output'),
	slot: slotSchema,
	label: v.string(),
	text: v.string()
});

export const assistantDeltaEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('assistant_delta'),
	slot: slotSchema,
	label: v.string(),
	delta: v.string(),
	text: v.string()
});

export const piEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('pi_event'),
	slot: slotSchema,
	label: v.string(),
	event: v.unknown()
});

export const piStderrEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('pi_stderr'),
	slot: slotSchema,
	label: v.string(),
	line: v.string()
});

export const sessionExitEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('session_exit'),
	slot: slotSchema,
	label: v.string(),
	code: v.nullable(v.number()),
	signal: nullableStringSchema
});

export const gitStatusEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('git_status'),
	slot: slotSchema,
	label: v.string(),
	status: v.string()
});

export const gitStatusErrorEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('git_status_error'),
	slot: slotSchema,
	label: v.string(),
	message: v.string()
});

export const checkpointCreatedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('checkpoint_created'),
	slot: slotSchema,
	label: v.string(),
	reason: v.string(),
	state: v.string()
});

export const bundleExportedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('bundle_exported'),
	slot: slotSchema,
	label: v.string(),
	bytes: v.pipe(v.number(), v.integer(), v.minValue(0)),
	path: v.string()
});

export const bundleImportedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('bundle_imported'),
	slot: slotSchema,
	label: v.string(),
	bytes: v.pipe(v.number(), v.integer(), v.minValue(0)),
	remoteName: v.string(),
	path: v.string()
});

const mergeResultEventBase = {
	...eventBaseSchema,
	slot: slotSchema,
	label: v.string(),
	remoteName: v.string(),
	branch: v.string(),
	exitCode: v.number(),
	output: v.string()
} as const;

export const gitMergeSucceededEventSchema = v.object({
	...mergeResultEventBase,
	type: v.literal('git_merge_succeeded')
});

export const gitMergeConflictedEventSchema = v.object({
	...mergeResultEventBase,
	type: v.literal('git_merge_conflicted')
});

export const forkPointRecordedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('fork_point_recorded'),
	slot: slotSchema,
	label: v.string(),
	reason: v.string(),
	path: v.string(),
	forkPoint: forkPointEventSummarySchema
});

export const forkSnapshotCreatedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('fork_snapshot_created'),
	slot: slotSchema,
	label: v.string(),
	image: v.string()
});

export const forkStartEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('fork_start'),
	sourceSlot: slotSchema,
	sourceLabel: v.string()
});

export const forkCompleteEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('fork_complete'),
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	targetLabel: v.string(),
	image: v.string(),
	forkPoint: forkPointArtifactSchema
});

export const mergePrepStartEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('merge_prep_start'),
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	remoteName: v.string()
});

export const mergePrepCompleteEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('merge_prep_complete'),
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	remoteName: v.string(),
	bytes: v.pipe(v.number(), v.integer(), v.minValue(0)),
	nextStep: v.string()
});

export const mergeStartEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('merge_start'),
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	sourceLabel: v.string(),
	targetLabel: v.string()
});

export const mergeIntegrationCreatedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('merge_integration_created'),
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	integrationSlot: slotSchema,
	integrationLabel: v.string(),
	integrationAgentUuid: v.string(),
	image: v.string(),
	forkPoint: forkPointArtifactSchema
});

export const mergeCompleteEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('merge_complete'),
	sourceSlot: slotSchema,
	targetSlot: slotSchema,
	integrationSlot: slotSchema,
	remoteName: v.string(),
	mergeExitCode: v.number(),
	mergeContextPath: v.string()
});

export const mergeContextWrittenEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('merge_context_written'),
	slot: slotSchema,
	label: v.string(),
	path: v.string()
});

export const workerContainerStartedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('worker_container_started'),
	slot: slotSchema,
	label: v.string(),
	containerName: v.string(),
	image: v.string(),
	agentUuid: v.string()
});

export const workerSocketClosedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('worker_socket_closed'),
	slot: slotSchema,
	label: v.string()
});

export const workerContainerRemovedEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('worker_container_removed'),
	slot: slotSchema,
	label: v.string(),
	containerName: v.string(),
	agentUuid: v.string()
});

export const bridgeErrorEventSchema = v.object({
	...eventBaseSchema,
	type: v.literal('bridge_error'),
	message: v.string(),
	raw: v.optional(v.string()),
	slot: v.optional(slotSchema),
	label: v.optional(v.string())
});

export const orchestratorEventSchema = v.variant('type', [
	gridBootEventSchema,
	gridReadyEventSchema,
	instanceCreatedEventSchema,
	instanceStoppedEventSchema,
	sessionReadyEventSchema,
	sessionOutputEventSchema,
	assistantDeltaEventSchema,
	piEventSchema,
	piStderrEventSchema,
	sessionExitEventSchema,
	gitStatusEventSchema,
	gitStatusErrorEventSchema,
	checkpointCreatedEventSchema,
	bundleExportedEventSchema,
	bundleImportedEventSchema,
	gitMergeSucceededEventSchema,
	gitMergeConflictedEventSchema,
	forkPointRecordedEventSchema,
	forkSnapshotCreatedEventSchema,
	forkStartEventSchema,
	forkCompleteEventSchema,
	mergePrepStartEventSchema,
	mergePrepCompleteEventSchema,
	mergeStartEventSchema,
	mergeIntegrationCreatedEventSchema,
	mergeCompleteEventSchema,
	mergeContextWrittenEventSchema,
	workerContainerStartedEventSchema,
	workerSocketClosedEventSchema,
	workerContainerRemovedEventSchema,
	bridgeErrorEventSchema
]);

export type ForkPointArtifact = v.InferOutput<typeof forkPointArtifactSchema>;
export type ForkPointEventSummary = v.InferOutput<typeof forkPointEventSummarySchema>;
export type MergeDetails = v.InferOutput<typeof mergeDetailsSchema>;
export type OrchestratorInstance = v.InferOutput<typeof orchestratorInstanceSchema>;
export type OrchestratorState = v.InferOutput<typeof orchestratorStateSchema>;
export type OrchestratorInstancesResponse = v.InferOutput<
	typeof orchestratorInstancesResponseSchema
>;
export type CreateInstanceResponse = v.InferOutput<typeof createInstanceResponseSchema>;
export type PromptInstanceResponse = v.InferOutput<typeof promptInstanceResponseSchema>;
export type ForkInstanceResponse = v.InferOutput<typeof forkInstanceResponseSchema>;
export type MergePrepResponse = v.InferOutput<typeof mergePrepResponseSchema>;
export type MergeResponse = v.InferOutput<typeof mergeResponseSchema>;
export type StopInstanceResponse = v.InferOutput<typeof stopInstanceResponseSchema>;
export type ApiErrorResponse = v.InferOutput<typeof apiErrorSchema>;
export type OrchestratorEvent = v.InferOutput<typeof orchestratorEventSchema>;
