import * as v from 'valibot';

import {
	createAgentNode,
	createAgentNodeId,
	createAgentNodePlacement,
	type AgentNode,
	type AgentNodeId,
	type AgentNodePlacement
} from '$lib/agent-graph/types';

export const explainModes = ['direct', 'ephemeral'] as const;
export type ExplainMode = (typeof explainModes)[number];

const explainModeSchema = v.picklist(explainModes);

const forkPointSummarySchema = v.object({
	format: v.optional(v.string()),
	markdown: v.optional(v.string()),
	preview: v.optional(v.nullable(v.string())),
	nodeTitle: v.optional(v.nullable(v.string())),
	readFiles: v.optional(v.array(v.string())),
	modifiedFiles: v.optional(v.array(v.string()))
});

const forkPointGitSchema = v.object({
	head: v.optional(v.nullable(v.string())),
	shortHead: v.optional(v.nullable(v.string())),
	status: v.optional(v.nullable(v.string())),
	subject: v.optional(v.nullable(v.string())),
	parents: v.optional(v.nullable(v.string())),
	shortStat: v.optional(v.nullable(v.string())),
	changedFiles: v.optional(v.array(v.string())),
	numStat: v.optional(v.array(v.string())),
	patch: v.optional(v.string())
});

const forkPointContextUsageSchema = v.object({
	assistantMessages: v.optional(v.number()),
	totalEntries: v.optional(v.number()),
	inputTokens: v.optional(v.number()),
	outputTokens: v.optional(v.number()),
	cacheReadTokens: v.optional(v.number()),
	cacheWriteTokens: v.optional(v.number()),
	totalTokens: v.optional(v.number()),
	latestResponseTokens: v.optional(v.number()),
	latestStopReason: v.optional(v.nullable(v.string()))
});

export const orchestratorForkPointSchema = v.looseObject({
	reason: v.optional(v.string()),
	capturedAt: v.optional(v.number()),
	slot: v.optional(v.number()),
	label: v.optional(v.string()),
	agentUuid: v.optional(v.string()),
	snapshotImage: v.optional(v.string()),
	git: v.optional(forkPointGitSchema),
	contextUsage: v.optional(forkPointContextUsageSchema),
	summary: v.optional(forkPointSummarySchema)
});

export type OrchestratorForkPoint = v.InferOutput<typeof orchestratorForkPointSchema>;

export const orchestratorInstanceSchema = v.object({
	slot: v.number(),
	label: v.string(),
	agentUuid: v.string(),
	containerName: v.nullable(v.string()),
	sessionId: v.nullable(v.string()),
	sourceImage: v.string(),
	status: v.picklist(['running', 'stopped']),
	lastGitStatus: v.nullable(v.string()),
	lastForkPoint: v.nullable(orchestratorForkPointSchema)
});

export type OrchestratorInstance = v.InferOutput<typeof orchestratorInstanceSchema>;

export const orchestratorStateSchema = v.object({
	sessionId: v.string(),
	model: v.string(),
	mergeModel: v.string(),
	instanceCount: v.number(),
	instances: v.array(orchestratorInstanceSchema)
});

export type OrchestratorState = v.InferOutput<typeof orchestratorStateSchema>;

export const explainFileResponseSchema = v.object({
	slot: v.number(),
	filePath: v.string(),
	mode: explainModeSchema,
	summary: v.string(),
	forkPointCapturedAt: v.number()
});

export type ExplainFileResponse = v.InferOutput<typeof explainFileResponseSchema>;

export type SlotLineage = Readonly<{
	parentSlot: number | null;
	mergedSourceSlots: readonly number[];
	forkPoint: OrchestratorForkPoint | null;
}>;

export type OrchestratorLineageState = Readonly<{
	bySlot: Readonly<Record<number, SlotLineage>>;
}>;

export type AgentExecutionState = 'running' | 'completed';
export type AgentExecutionStateBySlot = Readonly<Record<number, AgentExecutionState>>;
export type TerminalPreviewBySlot = Readonly<Record<number, string>>;

export function createEmptyLineageState(): OrchestratorLineageState {
	return { bySlot: {} };
}

function withSlotLineage(
	lineage: OrchestratorLineageState,
	slot: number,
	next: Partial<SlotLineage>
): OrchestratorLineageState {
	const current = lineage.bySlot[slot] ?? {
		parentSlot: null,
		mergedSourceSlots: [],
		forkPoint: null
	};

	return {
		bySlot: {
			...lineage.bySlot,
			[slot]: {
				parentSlot: next.parentSlot ?? current.parentSlot,
				mergedSourceSlots: next.mergedSourceSlots ?? current.mergedSourceSlots,
				forkPoint: next.forkPoint ?? current.forkPoint
			}
		}
	};
}

function readNumber(value: unknown): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function readForkPoint(value: unknown): OrchestratorForkPoint | null {
	const parsed = v.safeParse(orchestratorForkPointSchema, value);
	return parsed.success ? parsed.output : null;
}

export function applyOrchestratorEvent(
	lineage: OrchestratorLineageState,
	event: Record<string, unknown>
): OrchestratorLineageState {
	switch (event.type) {
		case 'fork_complete': {
			const sourceSlot = readNumber(event.sourceSlot);
			const targetSlot = readNumber(event.targetSlot);
			if (sourceSlot === null || targetSlot === null) return lineage;
			return withSlotLineage(lineage, targetSlot, {
				parentSlot: sourceSlot,
				forkPoint: readForkPoint(event.forkPoint)
			});
		}
		case 'merge_integration_created': {
			const sourceSlot = readNumber(event.sourceSlot);
			const targetSlot = readNumber(event.targetSlot);
			const integrationSlot = readNumber(event.integrationSlot);
			if (sourceSlot === null || targetSlot === null || integrationSlot === null) return lineage;
			return withSlotLineage(lineage, integrationSlot, {
				parentSlot: targetSlot,
				mergedSourceSlots: [sourceSlot],
				forkPoint: readForkPoint(event.forkPoint)
			});
		}
		case 'fork_point_recorded': {
			const slot = readNumber(event.slot);
			if (slot === null) return lineage;
			return withSlotLineage(lineage, slot, { forkPoint: readForkPoint(event.forkPoint) });
		}
		case 'instance_stopped': {
			const slot = readNumber(event.slot);
			if (slot === null || !(slot in lineage.bySlot)) return lineage;
			const nextBySlot = { ...lineage.bySlot };
			delete nextBySlot[slot];
			return { bySlot: nextBySlot };
		}
		default:
			return lineage;
	}
}

export function slotToAgentNodeId(slot: number): AgentNodeId {
	const suffix = slot.toString(16).padStart(12, '0').slice(-12);
	return createAgentNodeId(`00000000-0000-4000-8000-${suffix}`);
}

export function agentNodeIdToSlot(nodeId: AgentNodeId): number {
	const suffix = nodeId.slice(-12);
	return Number.parseInt(suffix, 16);
}

export function getResolvedForkPoint(
	instance: OrchestratorInstance,
	lineage: OrchestratorLineageState
): OrchestratorForkPoint | null {
	return lineage.bySlot[instance.slot]?.forkPoint ?? instance.lastForkPoint ?? null;
}

export function getInstanceExecutionState(
	slot: number,
	executionBySlot: AgentExecutionStateBySlot
): AgentExecutionState {
	return executionBySlot[slot] ?? 'completed';
}

function buildLiveOutputPreview(terminalText: string | undefined): readonly string[] {
	return String(terminalText || '')
		.split('\n')
		.map((line) => line.trimEnd())
		.filter((line) => line.trim().length > 0)
		.slice(-3)
		.map((line) => line.slice(0, 36));
}

export function buildAgentNodes(
	instances: readonly OrchestratorInstance[],
	lineage: OrchestratorLineageState,
	executionBySlot: AgentExecutionStateBySlot,
	terminalBySlot: TerminalPreviewBySlot = {}
): readonly AgentNode[] {
	const tokensBySlot = new Map(
		instances.map((instance) => [instance.slot, getResolvedForkPoint(instance, lineage)?.contextUsage?.totalTokens ?? 0])
	);
	const maxTokens = Math.max(1, ...tokensBySlot.values());

	return [...instances]
		.sort((left, right) => left.slot - right.slot)
		.map((instance) => {
			const slotLineage = lineage.bySlot[instance.slot] ?? null;
			const tokens = tokensBySlot.get(instance.slot) ?? 0;
			const percentage = tokens > 0 ? Math.max(1, Math.round((tokens / maxTokens) * 100)) : 0;
			const liveOutputPreview = buildLiveOutputPreview(terminalBySlot[instance.slot]);

			const preferredName =
				(instance.slot === 0 && !getResolvedForkPoint(instance, lineage)
					? 'Root'
					: null) ||
				getResolvedForkPoint(instance, lineage)?.summary?.nodeTitle?.trim() ||
				getResolvedForkPoint(instance, lineage)?.git?.subject?.trim() ||
				instance.label;

			return createAgentNode({
				id: slotToAgentNodeId(instance.slot),
				name: preferredName,
				parentId:
					slotLineage?.parentSlot !== null && slotLineage?.parentSlot !== undefined
						? slotToAgentNodeId(slotLineage.parentSlot)
						: null,
				mergedNodes: (slotLineage?.mergedSourceSlots ?? []).map((slot) => slotToAgentNodeId(slot)),
				status: getInstanceExecutionState(instance.slot, executionBySlot),
				details: {
					contextUsage: {
						tokens,
						percentage
					},
					liveOutputPreview
				}
			});
		});
}

export function buildBasePlacements(
	instances: readonly OrchestratorInstance[]
): readonly AgentNodePlacement[] {
	return [...instances]
		.sort((left, right) => left.slot - right.slot)
		.map((instance, index) => {
			const column = index % 4;
			const row = Math.floor(index / 4);
			return createAgentNodePlacement({
				nodeId: slotToAgentNodeId(instance.slot),
				x: (column - 1.5) * 260,
				y: row * 220 - 40 * (column % 2)
			});
		});
}
