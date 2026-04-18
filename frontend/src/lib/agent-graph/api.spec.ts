import { describe, expect, it } from 'vitest';
import { safeParse } from 'valibot';

import { fork, forkPromptSchema, merge } from './api';
import { createAgentNode } from './types';

describe('agent graph api scaffold', () => {
	it('exposes typed merge and fork entry points', () => {
		const baseNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440000',
			name: 'Base node',
			status: 'running'
		});
		const incomingNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440001',
			name: 'Incoming node',
			status: 'completed',
			parentId: baseNode.id
		});

		expect(merge(baseNode, incomingNode)).toBe(incomingNode);

		const forkedNode = fork(baseNode, 'Investigate auth edge cases');

		expect(forkedNode).toMatchObject({
			name: 'Investigate auth edge cases',
			parentId: baseNode.id,
			status: 'running',
			details: {
				contextUsage: { tokens: 0, percentage: 0 }
			}
		});
		expect(forkedNode.id).not.toBe(baseNode.id);
	});

	it('requires a non-empty fork prompt', () => {
		expect(safeParse(forkPromptSchema, 'Investigate auth edge cases').success).toBe(true);
		expect(safeParse(forkPromptSchema, '').success).toBe(false);
	});
});
