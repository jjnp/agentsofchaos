import {
	createAgentNode,
	createAgentNodeId,
	createAgentNodePlacement,
	type AgentNode,
	type AgentNodeId,
	type AgentNodePlacement,
	type AgentNodeStatus
} from '$lib/agent-graph/types';

import type {
	ForkPointArtifact,
	MergeDetails,
	OrchestratorEvent,
	OrchestratorInstance,
	OrchestratorState
} from './types';

export type ArtifactLoadStatus = 'idle' | 'loading' | 'ready' | 'missing' | 'error';
export type NodeTerminalMode = 'idle' | 'live' | 'replay';

export type ArtifactState<T> = Readonly<{
	status: ArtifactLoadStatus;
	data: T | null;
	error: string | null;
}>;

export type OrchestratorGraphNodeArtifacts = Readonly<{
	forkPoint: ArtifactState<ForkPointArtifact>;
	mergeDetails: ArtifactState<MergeDetails>;
	mergeContext: ArtifactState<string>;
}>;

export type OrchestratorGraphNodeBackend = Readonly<{
	slot: number;
	label: string;
	agentUuid: string;
	sessionId: string | null;
	containerName: string | null;
	sourceImage: string | null;
	instanceStatus: 'running' | 'stopped';
	gitStatus: string | null;
	parentSlot: number | null;
	mergedSourceSlots: readonly number[];
}>;

export type OrchestratorGraphNodeRecord = Readonly<{
	id: AgentNodeId;
	name: string;
	status: AgentNodeStatus;
	contextTokens: number;
	backend: OrchestratorGraphNodeBackend;
	terminalOutput: string;
	artifacts: OrchestratorGraphNodeArtifacts;
}>;

export type OrchestratorGraphState = Readonly<{
	sessionId: string | null;
	model: string | null;
	mergeModel: string | null;
	records: readonly OrchestratorGraphNodeRecord[];
	placements: readonly AgentNodePlacement[];
}>;

export type MaterializedOrchestratorGraphNode = Readonly<{
	node: AgentNode;
	record: OrchestratorGraphNodeRecord;
	placement: AgentNodePlacement | null;
	terminalMode: NodeTerminalMode;
}>;

const ROOT_X_STEP = 220;
const CHILD_X_OFFSET = 180;
const CHILD_Y_OFFSET = 108;
const CHILD_Y_STEP = 40;

const createArtifactState = <T>(status: ArtifactLoadStatus, data: T | null, error: string | null) =>
	({
		status,
		data,
		error
	}) satisfies ArtifactState<T>;

const createIdleArtifactState = <T>() => createArtifactState<T>('idle', null, null);

const createEmptyArtifacts = (): OrchestratorGraphNodeArtifacts => ({
	forkPoint: createIdleArtifactState<ForkPointArtifact>(),
	mergeDetails: createIdleArtifactState<MergeDetails>(),
	mergeContext: createIdleArtifactState<string>()
});

const createBackendState = (instance: OrchestratorInstance): OrchestratorGraphNodeBackend => ({
	slot: instance.slot,
	label: instance.label,
	agentUuid: instance.agentUuid,
	sessionId: instance.sessionId,
	containerName: instance.containerName,
	sourceImage: instance.sourceImage,
	instanceStatus: instance.status,
	gitStatus: instance.lastGitStatus,
	parentSlot: null,
	mergedSourceSlots: []
});

const getRecordIndexBySlot = (records: readonly OrchestratorGraphNodeRecord[], slot: number) =>
	records.findIndex((record) => record.backend.slot === slot);

const getRecordBySlot = (records: readonly OrchestratorGraphNodeRecord[], slot: number) =>
	records.find((record) => record.backend.slot === slot) ?? null;

const getSlotToNodeIdMap = (records: readonly OrchestratorGraphNodeRecord[]) =>
	new Map(records.map((record) => [record.backend.slot, record.id]));

const appendTerminalOutput = (currentOutput: string, nextChunk: string) =>
	nextChunk.length === 0 ? currentOutput : `${currentOutput}${nextChunk}`;

const deriveLineageFromForkPoint = (slot: number, forkPoint: ForkPointArtifact | null) => {
	if (!forkPoint) {
		return {
			parentSlot: null,
			mergedSourceSlots: [] as number[]
		};
	}

	if (forkPoint.reason === 'merge integration base' && forkPoint.slot !== slot) {
		return {
			parentSlot: forkPoint.mergeTargetSlot ?? forkPoint.slot,
			mergedSourceSlots:
				typeof forkPoint.mergeSourceSlot === 'number' ? [forkPoint.mergeSourceSlot] : []
		};
	}

	if (forkPoint.reason === 'fork' && forkPoint.slot !== slot) {
		return {
			parentSlot: forkPoint.slot,
			mergedSourceSlots: [] as number[]
		};
	}

	return {
		parentSlot: null,
		mergedSourceSlots: [] as number[]
	};
};

const countChildren = (records: readonly OrchestratorGraphNodeRecord[], parentSlot: number) =>
	records.filter((record) => record.backend.parentSlot === parentSlot).length;

const createPlacementForRecord = ({
	record,
	records,
	placements
}: {
	record: OrchestratorGraphNodeRecord;
	records: readonly OrchestratorGraphNodeRecord[];
	placements: readonly AgentNodePlacement[];
}): AgentNodePlacement => {
	const existingPlacement = placements.find((placement) => placement.nodeId === record.id);
	if (existingPlacement) {
		return existingPlacement;
	}

	if (record.backend.parentSlot === null) {
		const rootIndex =
			records.filter((candidate) => candidate.backend.parentSlot === null).length - 1;
		return createAgentNodePlacement({
			nodeId: record.id,
			x: rootIndex * ROOT_X_STEP,
			y: 0
		});
	}

	const parentRecord = getRecordBySlot(records, record.backend.parentSlot);
	const parentPlacement: AgentNodePlacement = parentRecord
		? (placements.find((placement) => placement.nodeId === parentRecord.id) ??
			createPlacementForRecord({ record: parentRecord, records, placements }))
		: createAgentNodePlacement({ nodeId: record.id, x: 0, y: 0 });
	const siblingIndex = Math.max(countChildren(records, record.backend.parentSlot) - 1, 0);

	return createAgentNodePlacement({
		nodeId: record.id,
		x: parentPlacement.x + CHILD_X_OFFSET,
		y: parentPlacement.y + CHILD_Y_OFFSET + siblingIndex * CHILD_Y_STEP
	});
};

const upsertPlacement = (
	placements: readonly AgentNodePlacement[],
	record: OrchestratorGraphNodeRecord,
	records: readonly OrchestratorGraphNodeRecord[]
) => {
	if (placements.some((placement) => placement.nodeId === record.id)) {
		return placements;
	}

	return [...placements, createPlacementForRecord({ record, records, placements })];
};

const upsertRecord = (
	state: OrchestratorGraphState,
	record: OrchestratorGraphNodeRecord
): OrchestratorGraphState => {
	const existingIndex = getRecordIndexBySlot(state.records, record.backend.slot);
	const nextRecords = [...state.records];
	if (existingIndex === -1) {
		nextRecords.push(record);
	} else {
		nextRecords[existingIndex] = record;
	}

	const sortedRecords = nextRecords.sort((left, right) => left.backend.slot - right.backend.slot);
	return {
		...state,
		records: sortedRecords,
		placements: upsertPlacement(state.placements, record, sortedRecords)
	};
};

const removeRecordBySlot = (
	state: OrchestratorGraphState,
	slot: number
): OrchestratorGraphState => {
	const record = getRecordBySlot(state.records, slot);
	if (!record) {
		return state;
	}

	return {
		...state,
		records: state.records.filter((candidate) => candidate.backend.slot !== slot),
		placements: state.placements.filter((placement) => placement.nodeId !== record.id)
	};
};

const toMaterializedNode = (
	record: OrchestratorGraphNodeRecord,
	records: readonly OrchestratorGraphNodeRecord[],
	maxContextTokens: number,
	placement: AgentNodePlacement | null
): MaterializedOrchestratorGraphNode => {
	const slotToNodeId = getSlotToNodeIdMap(records);
	const contextPercentage =
		maxContextTokens > 0 ? Math.round((record.contextTokens / maxContextTokens) * 100) : 0;
	const node = createAgentNode({
		id: record.id,
		name: record.name,
		parentId:
			record.backend.parentSlot !== null
				? (slotToNodeId.get(record.backend.parentSlot) ?? null)
				: null,
		mergedNodes: record.backend.mergedSourceSlots
			.map((slot) => slotToNodeId.get(slot))
			.filter((value): value is AgentNodeId => value !== undefined),
		status: record.status,
		details: {
			contextUsage: {
				tokens: record.contextTokens,
				percentage: contextPercentage
			}
		}
	});

	return {
		node,
		record,
		placement,
		terminalMode:
			record.terminalOutput.length === 0 ? 'idle' : record.status === 'running' ? 'live' : 'replay'
	};
};

export const createOrchestratorGraphState = (): OrchestratorGraphState => ({
	sessionId: null,
	model: null,
	mergeModel: null,
	records: [],
	placements: []
});

export const materializeOrchestratorGraph = (state: OrchestratorGraphState) => {
	const maxContextTokens = state.records.reduce(
		(max, record) => Math.max(max, record.contextTokens),
		0
	);
	const nodes = state.records.map((record) =>
		toMaterializedNode(
			record,
			state.records,
			maxContextTokens,
			state.placements.find((placement) => placement.nodeId === record.id) ?? null
		)
	);

	return {
		runtimeNodes: nodes,
		nodes: nodes.map((entry) => entry.node),
		placements: nodes.flatMap((entry) => (entry.placement ? [entry.placement] : []))
	};
};

export const bootstrapOrchestratorGraph = ({
	state,
	orchestratorState,
	forkPointsBySlot
}: {
	state: OrchestratorGraphState;
	orchestratorState: OrchestratorState;
	forkPointsBySlot?: ReadonlyMap<number, ForkPointArtifact | null>;
}): OrchestratorGraphState => {
	let nextState: OrchestratorGraphState = {
		...state,
		sessionId: orchestratorState.sessionId,
		model: orchestratorState.model,
		mergeModel: orchestratorState.mergeModel,
		records: [],
		placements: state.placements.filter((placement) =>
			state.records.some((record) => record.id === placement.nodeId)
		)
	};

	for (const instance of orchestratorState.instances.sort(
		(left, right) => left.slot - right.slot
	)) {
		const existingRecord = getRecordBySlot(state.records, instance.slot);
		const forkPoint = forkPointsBySlot?.get(instance.slot) ?? null;
		const lineage = deriveLineageFromForkPoint(instance.slot, forkPoint);
		const record: OrchestratorGraphNodeRecord = {
			id: existingRecord?.id ?? createAgentNodeId(),
			name: existingRecord?.name ?? instance.label,
			status: existingRecord?.status ?? 'completed',
			contextTokens: forkPoint?.contextUsage.totalTokens ?? existingRecord?.contextTokens ?? 0,
			backend: {
				...createBackendState(instance),
				parentSlot: lineage.parentSlot,
				mergedSourceSlots: lineage.mergedSourceSlots
			},
			terminalOutput: existingRecord?.terminalOutput ?? '',
			artifacts: {
				forkPoint: forkPoint
					? createArtifactState('ready', forkPoint, null)
					: (existingRecord?.artifacts.forkPoint ?? createIdleArtifactState<ForkPointArtifact>()),
				mergeDetails:
					existingRecord?.artifacts.mergeDetails ?? createIdleArtifactState<MergeDetails>(),
				mergeContext: existingRecord?.artifacts.mergeContext ?? createIdleArtifactState<string>()
			}
		};
		nextState = upsertRecord(nextState, record);
	}

	return {
		...nextState,
		placements: nextState.placements.filter((placement) =>
			nextState.records.some((record) => record.id === placement.nodeId)
		)
	};
};

export const reduceOrchestratorGraphEvent = (
	state: OrchestratorGraphState,
	event: OrchestratorEvent
): OrchestratorGraphState => {
	switch (event.type) {
		case 'grid_boot':
			return {
				...state,
				sessionId: event.session,
				model: event.model,
				mergeModel: event.mergeModel
			};
		case 'instance_stopped':
			return removeRecordBySlot(state, event.slot);
		case 'instance_created': {
			const existingRecord = getRecordBySlot(state.records, event.slot);
			return upsertRecord(state, {
				id: existingRecord?.id ?? createAgentNodeId(),
				name: existingRecord?.name ?? event.label,
				status: existingRecord?.status ?? 'completed',
				contextTokens: existingRecord?.contextTokens ?? 0,
				backend: {
					slot: event.slot,
					label: event.label,
					agentUuid: event.agentUuid,
					sessionId: existingRecord?.backend.sessionId ?? null,
					containerName: existingRecord?.backend.containerName ?? null,
					sourceImage: existingRecord?.backend.sourceImage ?? null,
					instanceStatus: 'running',
					gitStatus: existingRecord?.backend.gitStatus ?? null,
					parentSlot: existingRecord?.backend.parentSlot ?? null,
					mergedSourceSlots: existingRecord?.backend.mergedSourceSlots ?? []
				},
				terminalOutput: existingRecord?.terminalOutput ?? '',
				artifacts: existingRecord?.artifacts ?? createEmptyArtifacts()
			});
		}
		case 'worker_container_started':
		case 'session_ready': {
			const existingRecord = getRecordBySlot(state.records, event.slot);
			const record: OrchestratorGraphNodeRecord = {
				id: existingRecord?.id ?? createAgentNodeId(),
				name: existingRecord?.name ?? event.label,
				status: existingRecord?.status ?? 'completed',
				contextTokens: existingRecord?.contextTokens ?? 0,
				backend: {
					slot: event.slot,
					label: event.label,
					agentUuid: event.agentUuid,
					sessionId:
						event.type === 'session_ready'
							? event.sessionId
							: (existingRecord?.backend.sessionId ?? null),
					containerName:
						event.type === 'worker_container_started'
							? event.containerName
							: (existingRecord?.backend.containerName ?? null),
					sourceImage:
						event.type === 'worker_container_started'
							? event.image
							: (existingRecord?.backend.sourceImage ?? null),
					instanceStatus: 'running',
					gitStatus: existingRecord?.backend.gitStatus ?? null,
					parentSlot: existingRecord?.backend.parentSlot ?? null,
					mergedSourceSlots: existingRecord?.backend.mergedSourceSlots ?? []
				},
				terminalOutput: existingRecord?.terminalOutput ?? '',
				artifacts: existingRecord?.artifacts ?? createEmptyArtifacts()
			};

			return upsertRecord(state, record);
		}
		case 'session_output':
		case 'pi_stderr': {
			const existingRecord = getRecordBySlot(state.records, event.slot);
			if (!existingRecord) {
				return state;
			}
			return upsertRecord(state, {
				...existingRecord,
				terminalOutput: appendTerminalOutput(
					existingRecord.terminalOutput,
					event.type === 'session_output' ? event.text : `! stderr ${event.line}\n`
				)
			});
		}
		case 'session_exit': {
			const existingRecord = getRecordBySlot(state.records, event.slot);
			if (!existingRecord) {
				return state;
			}
			return upsertRecord(state, {
				...existingRecord,
				status: 'completed',
				terminalOutput: appendTerminalOutput(
					existingRecord.terminalOutput,
					`\n! exited code=${event.code ?? 'null'} signal=${event.signal ?? 'none'}\n`
				)
			});
		}
		case 'git_status': {
			const existingRecord = getRecordBySlot(state.records, event.slot);
			if (!existingRecord) {
				return state;
			}
			return upsertRecord(state, {
				...existingRecord,
				backend: {
					...existingRecord.backend,
					gitStatus: event.status
				}
			});
		}
		case 'fork_point_recorded': {
			const existingRecord = getRecordBySlot(state.records, event.slot);
			if (!existingRecord) {
				return state;
			}
			return upsertRecord(state, {
				...existingRecord,
				contextTokens: event.forkPoint.contextUsage.totalTokens,
				artifacts: {
					...existingRecord.artifacts,
					forkPoint: createArtifactState(
						'ready',
						{
							...existingRecord.artifacts.forkPoint.data,
							...event.forkPoint,
							label: existingRecord.backend.label,
							agentUuid: existingRecord.backend.agentUuid,
							slot: event.slot,
							git: {
								head: null,
								shortHead: event.forkPoint.git.shortHead,
								status: existingRecord.backend.gitStatus,
								subject: null,
								parents: null,
								shortStat: event.forkPoint.git.shortStat,
								changedFiles: event.forkPoint.git.changedFiles,
								numStat: [],
								patch: ''
							},
							session: {
								path: null,
								latestEntryId: null,
								totalEntries: 0,
								assistantMessages: event.forkPoint.contextUsage.assistantMessages,
								latestStopReason: null
							},
							contextUsage: {
								assistantMessages: event.forkPoint.contextUsage.assistantMessages,
								totalEntries: 0,
								inputTokens: 0,
								outputTokens: 0,
								cacheReadTokens: 0,
								cacheWriteTokens: 0,
								totalTokens: event.forkPoint.contextUsage.totalTokens,
								latestResponseTokens: event.forkPoint.contextUsage.latestResponseTokens,
								latestStopReason: null
							},
							summary: {
								format: event.forkPoint.summary.format,
								markdown: event.forkPoint.summary.preview ?? '',
								preview: event.forkPoint.summary.preview,
								readFiles: event.forkPoint.summary.readFiles,
								modifiedFiles: event.forkPoint.summary.modifiedFiles
							},
							reason: event.reason,
							capturedAt: event.forkPoint.capturedAt
						},
						null
					)
				}
			});
		}
		case 'fork_complete': {
			const existingRecord = getRecordBySlot(state.records, event.targetSlot);
			return upsertRecord(state, {
				id: existingRecord?.id ?? createAgentNodeId(),
				name: existingRecord?.name ?? event.targetLabel,
				status: 'completed',
				contextTokens: event.forkPoint.contextUsage.totalTokens,
				backend: {
					slot: event.targetSlot,
					label: event.targetLabel,
					agentUuid: existingRecord?.backend.agentUuid ?? `pending-agent-${event.targetSlot}`,
					sessionId: existingRecord?.backend.sessionId ?? null,
					containerName: existingRecord?.backend.containerName ?? null,
					sourceImage: event.image,
					instanceStatus: 'running',
					gitStatus: existingRecord?.backend.gitStatus ?? null,
					parentSlot: event.sourceSlot,
					mergedSourceSlots: []
				},
				terminalOutput: existingRecord?.terminalOutput ?? '',
				artifacts: {
					...(existingRecord?.artifacts ?? createEmptyArtifacts()),
					forkPoint: createArtifactState('ready', event.forkPoint, null)
				}
			});
		}
		case 'merge_integration_created': {
			const existingRecord = getRecordBySlot(state.records, event.integrationSlot);
			return upsertRecord(state, {
				id: existingRecord?.id ?? createAgentNodeId(),
				name: existingRecord?.name ?? event.integrationLabel,
				status: 'running',
				contextTokens: event.forkPoint.contextUsage.totalTokens,
				backend: {
					slot: event.integrationSlot,
					label: event.integrationLabel,
					agentUuid: event.integrationAgentUuid,
					sessionId: existingRecord?.backend.sessionId ?? null,
					containerName: existingRecord?.backend.containerName ?? null,
					sourceImage: event.image,
					instanceStatus: 'running',
					gitStatus: existingRecord?.backend.gitStatus ?? null,
					parentSlot: event.targetSlot,
					mergedSourceSlots: [event.sourceSlot]
				},
				terminalOutput: existingRecord?.terminalOutput ?? '',
				artifacts: {
					...(existingRecord?.artifacts ?? createEmptyArtifacts()),
					forkPoint: createArtifactState('ready', event.forkPoint, null)
				}
			});
		}
		case 'merge_complete': {
			const existingRecord = getRecordBySlot(state.records, event.integrationSlot);
			if (!existingRecord) {
				return state;
			}
			return upsertRecord(state, {
				...existingRecord,
				status: 'completed'
			});
		}
		case 'bridge_error': {
			if (typeof event.slot !== 'number') {
				return state;
			}
			const existingRecord = getRecordBySlot(state.records, event.slot);
			if (!existingRecord) {
				return state;
			}
			return upsertRecord(state, {
				...existingRecord,
				terminalOutput: appendTerminalOutput(
					existingRecord.terminalOutput,
					`\n! error ${event.message}\n`
				)
			});
		}
		case 'pi_event': {
			const existingRecord = getRecordBySlot(state.records, event.slot);
			if (!existingRecord || typeof event.event !== 'object' || event.event === null) {
				return state;
			}
			const eventType = 'type' in event.event ? event.event.type : null;
			if (eventType === 'agent_start') {
				return upsertRecord(state, {
					...existingRecord,
					status: 'running'
				});
			}
			if (eventType === 'agent_end') {
				return upsertRecord(state, {
					...existingRecord,
					status: 'completed'
				});
			}
			return state;
		}
		default:
			return state;
	}
};

export const markNodePromptQueued = (
	state: OrchestratorGraphState,
	slot: number
): OrchestratorGraphState => {
	const existingRecord = getRecordBySlot(state.records, slot);
	if (!existingRecord) {
		return state;
	}

	return upsertRecord(state, {
		...existingRecord,
		status: 'running'
	});
};

export const setForkPointArtifactState = (
	state: OrchestratorGraphState,
	slot: number,
	artifact: ArtifactState<ForkPointArtifact>
): OrchestratorGraphState => {
	const existingRecord = getRecordBySlot(state.records, slot);
	if (!existingRecord) {
		return state;
	}

	const lineage = deriveLineageFromForkPoint(slot, artifact.data);
	return upsertRecord(state, {
		...existingRecord,
		contextTokens: artifact.data?.contextUsage.totalTokens ?? existingRecord.contextTokens,
		backend: {
			...existingRecord.backend,
			parentSlot: lineage.parentSlot,
			mergedSourceSlots: lineage.mergedSourceSlots
		},
		artifacts: {
			...existingRecord.artifacts,
			forkPoint: artifact
		}
	});
};

export const setMergeDetailsArtifactState = (
	state: OrchestratorGraphState,
	slot: number,
	artifact: ArtifactState<MergeDetails>
): OrchestratorGraphState => {
	const existingRecord = getRecordBySlot(state.records, slot);
	if (!existingRecord) {
		return state;
	}

	return upsertRecord(state, {
		...existingRecord,
		artifacts: {
			...existingRecord.artifacts,
			mergeDetails: artifact
		}
	});
};

export const setMergeContextArtifactState = (
	state: OrchestratorGraphState,
	slot: number,
	artifact: ArtifactState<string>
): OrchestratorGraphState => {
	const existingRecord = getRecordBySlot(state.records, slot);
	if (!existingRecord) {
		return state;
	}

	return upsertRecord(state, {
		...existingRecord,
		artifacts: {
			...existingRecord.artifacts,
			mergeContext: artifact
		}
	});
};

export const getRuntimeNodeById = (
	state: OrchestratorGraphState,
	nodeId: AgentNodeId | null
): MaterializedOrchestratorGraphNode | null => {
	if (!nodeId) {
		return null;
	}

	return (
		materializeOrchestratorGraph(state).runtimeNodes.find((entry) => entry.node.id === nodeId) ??
		null
	);
};

export const getSlotForNodeId = (
	state: OrchestratorGraphState,
	nodeId: AgentNodeId | null
): number | null => {
	if (!nodeId) {
		return null;
	}

	return state.records.find((record) => record.id === nodeId)?.backend.slot ?? null;
};

export const createLoadingArtifactState = <T>() => createArtifactState<T>('loading', null, null);
export const createMissingArtifactState = <T>() => createArtifactState<T>('missing', null, null);
export const createErrorArtifactState = <T>(error: string) =>
	createArtifactState<T>('error', null, error);
export const createReadyArtifactState = <T>(data: T) => createArtifactState<T>('ready', data, null);
