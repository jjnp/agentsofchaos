import { safeParse } from 'valibot';
import { describe, expect, it } from 'vitest';

import {
	agentNodePlacementSchema,
	agentNodeSchema,
	createAgentNode,
	createAgentNodePlacement,
	isAgentNodeId,
	type AgentNode
} from './types';

describe('agent graph schemas', () => {
	it('accepts valid agent nodes with UUID ids', () => {
		const node = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440000',
			name: 'Root node'
		});

		expect(safeParse(agentNodeSchema, node).success).toBe(true);
		expect(isAgentNodeId(node.id)).toBe(true);
	});

	it('keeps node placement separate from node identity', () => {
		const placement = createAgentNodePlacement({
			nodeId: '550e8400-e29b-41d4-a716-446655440000',
			x: 120,
			y: 80
		});

		expect(safeParse(agentNodePlacementSchema, placement).success).toBe(true);
		if (!('x' in placement)) {
			throw new Error('Expected placement to include coordinates.');
		}
	});

	it('rejects invalid node ids', () => {
		const invalidNode = {
			id: 'not-a-uuid',
			name: 'Broken node',
			parentId: null
		} satisfies Omit<AgentNode, 'id' | 'parentId'> & {
			id: string;
			parentId: string | null;
		};

		expect(safeParse(agentNodeSchema, invalidNode).success).toBe(false);
		expect(isAgentNodeId(invalidNode.id)).toBe(false);
	});
});
