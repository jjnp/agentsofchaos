import { describe, expect, it } from 'vitest';

import {
	bootstrapOrchestratorGraph,
	createOrchestratorGraphState,
	createReadyArtifactState,
	getRuntimeNodeById,
	getSlotForNodeId,
	markNodePromptQueued,
	materializeOrchestratorGraph,
	reduceOrchestratorGraphEvent,
	setMergeContextArtifactState
} from './graph';
import type { ForkPointArtifact, OrchestratorState } from './types';

const createForkPointArtifact = (input: {
	slot: number;
	reason: string;
	mergeSourceSlot?: number;
	mergeTargetSlot?: number;
	totalTokens?: number;
}): ForkPointArtifact => ({
	reason: input.reason,
	capturedAt: 1776510000000,
	slot: input.slot,
	label: `pi-${input.slot + 1}`,
	agentUuid: `piagent_${input.slot}`,
	git: {
		head: null,
		shortHead: null,
		status: null,
		subject: null,
		parents: null,
		shortStat: null,
		changedFiles: [],
		numStat: [],
		patch: ''
	},
	session: {
		path: null,
		latestEntryId: null,
		totalEntries: 0,
		assistantMessages: 0,
		latestStopReason: null
	},
	contextUsage: {
		assistantMessages: 0,
		totalEntries: 0,
		inputTokens: 0,
		outputTokens: 0,
		cacheReadTokens: 0,
		cacheWriteTokens: 0,
		totalTokens: input.totalTokens ?? 0,
		latestResponseTokens: 0,
		latestStopReason: null
	},
	summary: {
		format: 'pi-branch-summary-v1',
		markdown: '# Summary',
		preview: 'Summary',
		readFiles: [],
		modifiedFiles: []
	},
	...(typeof input.mergeSourceSlot === 'number' ? { mergeSourceSlot: input.mergeSourceSlot } : {}),
	...(typeof input.mergeTargetSlot === 'number' ? { mergeTargetSlot: input.mergeTargetSlot } : {})
});

describe('orchestrator graph reducer', () => {
	it('bootstraps graph records with fork and merge lineage from artifacts', () => {
		const orchestratorState: OrchestratorState = {
			sessionId: 'session-1',
			model: 'openai/gpt-5.4-mini',
			mergeModel: 'gpt-5.4-mini',
			instanceCount: 3,
			instances: [
				{
					slot: 0,
					label: 'pi-1',
					agentUuid: 'piagent_0',
					containerName: 'aoc-piagent_0',
					sessionId: 'worker-0',
					sourceImage: 'agentsofchaos/pi-worker:latest',
					status: 'running',
					lastGitStatus: null,
					lastForkPoint: null
				},
				{
					slot: 1,
					label: 'pi-2',
					agentUuid: 'piagent_1',
					containerName: 'aoc-piagent_1',
					sessionId: 'worker-1',
					sourceImage: 'agentsofchaos/pi-snapshot:fork',
					status: 'running',
					lastGitStatus: null,
					lastForkPoint: null
				},
				{
					slot: 2,
					label: 'pi-3',
					agentUuid: 'piagent_2',
					containerName: 'aoc-piagent_2',
					sessionId: 'worker-2',
					sourceImage: 'agentsofchaos/pi-snapshot:merge',
					status: 'running',
					lastGitStatus: null,
					lastForkPoint: null
				}
			]
		};

		const graphState = bootstrapOrchestratorGraph({
			state: createOrchestratorGraphState(),
			orchestratorState,
			forkPointsBySlot: new Map([
				[1, createForkPointArtifact({ slot: 0, reason: 'fork', totalTokens: 120 })],
				[
					2,
					createForkPointArtifact({
						slot: 1,
						reason: 'merge integration base',
						mergeSourceSlot: 0,
						mergeTargetSlot: 1,
						totalTokens: 260
					})
				]
			])
		});
		const graph = materializeOrchestratorGraph(graphState);

		expect(graph.nodes).toHaveLength(3);
		expect(graph.nodes[1]).toMatchObject({ parentId: graph.nodes[0]?.id });
		expect(graph.nodes[2]).toMatchObject({
			parentId: graph.nodes[1]?.id,
			mergedNodes: [graph.nodes[0]?.id]
		});
		expect(graph.nodes[2]?.details?.contextUsage.percentage).toBe(100);
	});

	it('marks prompt runs as running and finishes them on agent_end', () => {
		let state = bootstrapOrchestratorGraph({
			state: createOrchestratorGraphState(),
			orchestratorState: {
				sessionId: 'session-1',
				model: 'openai/gpt-5.4-mini',
				mergeModel: 'gpt-5.4-mini',
				instanceCount: 1,
				instances: [
					{
						slot: 0,
						label: 'pi-1',
						agentUuid: 'piagent_0',
						containerName: 'aoc-piagent_0',
						sessionId: 'worker-0',
						sourceImage: 'agentsofchaos/pi-worker:latest',
						status: 'running',
						lastGitStatus: null,
						lastForkPoint: null
					}
				]
			}
		});

		state = markNodePromptQueued(state, 0);
		expect(materializeOrchestratorGraph(state).nodes[0]?.status).toBe('running');

		state = reduceOrchestratorGraphEvent(state, {
			type: 'session_output',
			slot: 0,
			label: 'pi-1',
			text: '> user hello\n'
		});
		state = reduceOrchestratorGraphEvent(state, {
			type: 'pi_event',
			slot: 0,
			label: 'pi-1',
			event: {
				type: 'agent_end'
			}
		});

		const runtimeNode = materializeOrchestratorGraph(state).runtimeNodes[0];
		expect(runtimeNode?.node.status).toBe('completed');
		expect(runtimeNode?.record.terminalOutput).toContain('> user hello');
		expect(runtimeNode?.terminalMode).toBe('replay');
	});

	it('stores merge context artifacts on selected integration nodes', () => {
		let state = bootstrapOrchestratorGraph({
			state: createOrchestratorGraphState(),
			orchestratorState: {
				sessionId: 'session-1',
				model: 'openai/gpt-5.4-mini',
				mergeModel: 'gpt-5.4-mini',
				instanceCount: 1,
				instances: [
					{
						slot: 2,
						label: 'pi-3',
						agentUuid: 'piagent_2',
						containerName: 'aoc-piagent_2',
						sessionId: 'worker-2',
						sourceImage: 'agentsofchaos/pi-snapshot:merge',
						status: 'running',
						lastGitStatus: null,
						lastForkPoint: null
					}
				]
			}
		});
		const nodeId = state.records[0]?.id ?? null;

		state = setMergeContextArtifactState(
			state,
			2,
			createReadyArtifactState('# Merge Context\n\n## Combined Intent')
		);
		const runtimeNode = getRuntimeNodeById(state, nodeId);

		expect(runtimeNode?.record.artifacts.mergeContext.status).toBe('ready');
		expect(runtimeNode?.record.artifacts.mergeContext.data).toContain('Combined Intent');
		expect(getSlotForNodeId(state, nodeId)).toBe(2);
	});
});
