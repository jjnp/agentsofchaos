import { describe, expect, it } from 'vitest';

import {
	applyOrchestratorEvent,
	buildAgentNodes,
	createEmptyLineageState,
	slotToAgentNodeId,
	type OrchestratorInstance
} from './contracts';

describe('orchestrator graph contracts', () => {
	it('records lineage for forked and merge-integration instances', () => {
		let lineage = createEmptyLineageState();
		lineage = applyOrchestratorEvent(lineage, {
			type: 'fork_complete',
			sourceSlot: 0,
			targetSlot: 1,
			forkPoint: {
				summary: { markdown: '## Goal\nFork child', preview: 'Fork child' },
				contextUsage: { totalTokens: 400 }
			}
		});
		lineage = applyOrchestratorEvent(lineage, {
			type: 'merge_integration_created',
			sourceSlot: 1,
			targetSlot: 0,
			integrationSlot: 2,
			forkPoint: {
				summary: { markdown: '## Goal\nMerge integration', preview: 'Merge integration' }
			}
		});

		expect(lineage.bySlot[1]).toMatchObject({
			parentSlot: 0,
			mergedSourceSlots: []
		});
		expect(lineage.bySlot[2]).toMatchObject({
			parentSlot: 0,
			mergedSourceSlots: [1]
		});
	});

	it('builds agent nodes from live instances plus event-derived lineage', () => {
		const instances: OrchestratorInstance[] = [
			{
				slot: 0,
				label: 'pi-1',
				agentUuid: 'piagent_root',
				containerName: 'aoc-root',
				sessionId: null,
				sourceImage: 'agentsofchaos/pi-worker:latest',
				status: 'running',
				lastGitStatus: '## main',
				lastForkPoint: null
			},
			{
				slot: 1,
				label: 'pi-2',
				agentUuid: 'piagent_child',
				containerName: 'aoc-child',
				sessionId: null,
				sourceImage: 'agentsofchaos/pi-snapshot:child',
				status: 'running',
				lastGitStatus: '## main',
				lastForkPoint: null
			}
		];

		const lineage = applyOrchestratorEvent(createEmptyLineageState(), {
			type: 'fork_complete',
			sourceSlot: 0,
			targetSlot: 1,
			forkPoint: {
				contextUsage: { totalTokens: 900 }
			}
		});
		const nodes = buildAgentNodes(instances, lineage, { 1: 'running' }, { 1: 'line one\nline two\nline three\nline four' });

		expect(nodes).toHaveLength(2);
		expect(nodes[1]).toMatchObject({
			id: slotToAgentNodeId(1),
			parentId: slotToAgentNodeId(0),
			status: 'running'
		});
		expect(nodes[1]?.details?.contextUsage.tokens).toBe(900);
		expect(nodes[1]?.details?.liveOutputPreview).toEqual(['line two', 'line three', 'line four']);
	});
});
