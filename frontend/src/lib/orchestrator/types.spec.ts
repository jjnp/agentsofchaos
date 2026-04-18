import { describe, expect, it } from 'vitest';
import { safeParse } from 'valibot';

import {
	forkPointArtifactSchema,
	mergeResponseSchema,
	orchestratorEventSchema,
	orchestratorStateSchema
} from './types';

describe('orchestrator schemas', () => {
	it('parses orchestrator state responses', () => {
		const result = safeParse(orchestratorStateSchema, {
			sessionId: 'b49645d87d60',
			model: 'openai/gpt-5.4-mini',
			mergeModel: 'gpt-5.4-mini',
			instanceCount: 1,
			instances: [
				{
					slot: 0,
					label: 'pi-1',
					agentUuid: 'piagent_example',
					containerName: 'aoc-piagent_example',
					sessionId: 'session-1',
					sourceImage: 'agentsofchaos/pi-worker:latest',
					status: 'running',
					lastGitStatus: '## main...origin/main',
					lastForkPoint: null
				}
			]
		});

		expect(result.success).toBe(true);
	});

	it('parses fork-point artifacts', () => {
		const result = safeParse(forkPointArtifactSchema, {
			reason: 'fork',
			capturedAt: 1776510000000,
			slot: 1,
			label: 'pi-2',
			agentUuid: 'piagent_example',
			git: {
				head: 'abc123def456ghi789',
				shortHead: 'abc123def456',
				status: '## main',
				subject: 'feat: branch work',
				parents: 'abc123 def456',
				shortStat: '2 files changed, 10 insertions(+), 3 deletions(-)',
				changedFiles: ['src/foo.ts'],
				numStat: ['10\t3\tsrc/foo.ts'],
				patch: 'diff --git a/src/foo.ts b/src/foo.ts'
			},
			session: {
				path: '/state/pi-agent/sessions/latest.jsonl',
				latestEntryId: 'entry-1',
				totalEntries: 4,
				assistantMessages: 2,
				latestStopReason: 'end_turn'
			},
			contextUsage: {
				assistantMessages: 2,
				totalEntries: 4,
				inputTokens: 10,
				outputTokens: 12,
				cacheReadTokens: 0,
				cacheWriteTokens: 0,
				totalTokens: 22,
				latestResponseTokens: 12,
				latestStopReason: 'end_turn'
			},
			summary: {
				format: 'pi-branch-summary-v1',
				markdown: '## Goal\nWork on feature X',
				preview: 'Work on feature X',
				readFiles: ['src/foo.ts'],
				modifiedFiles: ['src/foo.ts']
			}
		});

		expect(result.success).toBe(true);
	});

	it('parses merge lifecycle events', () => {
		const event = safeParse(orchestratorEventSchema, {
			type: 'merge_complete',
			sourceSlot: 1,
			targetSlot: 0,
			integrationSlot: 3,
			remoteName: 'merge_slot_2',
			mergeExitCode: 0,
			mergeContextPath: '/state/meta/merge-context.md'
		});

		expect(event.success).toBe(true);
	});

	it('parses merge responses', () => {
		const result = safeParse(mergeResponseSchema, {
			sourceSlot: 1,
			targetSlot: 0,
			integrationSlot: 3,
			remoteName: 'merge_slot_2',
			mergeExitCode: 0,
			mergeContextPath: '/state/meta/merge-context.md'
		});

		expect(result.success).toBe(true);
	});
});
