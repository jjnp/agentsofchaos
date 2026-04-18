import { createAgentNode, createAgentNodePlacement } from './types';

export const demoAgentNodes = [
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440000',
		name: 'Root',
		parentId: null
	}),
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440001',
		name: 'Token rotation',
		parentId: '550e8400-e29b-41d4-a716-446655440000'
	}),
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440002',
		name: 'Silent refresh',
		parentId: '550e8400-e29b-41d4-a716-446655440001'
	}),
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440003',
		name: 'Inline cleanup',
		parentId: '550e8400-e29b-41d4-a716-446655440000'
	}),
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440004',
		name: 'Protocol spec',
		parentId: '550e8400-e29b-41d4-a716-446655440001'
	}),
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440005',
		name: 'Redis bench',
		parentId: '550e8400-e29b-41d4-a716-446655440001'
	}),
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440006',
		name: 'Threat model',
		parentId: '550e8400-e29b-41d4-a716-446655440001'
	}),
	createAgentNode({
		id: '550e8400-e29b-41d4-a716-446655440007',
		name: 'Type patch',
		parentId: '550e8400-e29b-41d4-a716-446655440003'
	})
] as const;

export const demoAgentNodePlacements = [
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440000', x: 0, y: 0 }),
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440001', x: -220, y: 12 }),
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440002', x: -12, y: -210 }),
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440003', x: 0, y: 180 }),
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440004', x: -430, y: 110 }),
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440005', x: -560, y: -64 }),
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440006', x: -520, y: 290 }),
	createAgentNodePlacement({ nodeId: '550e8400-e29b-41d4-a716-446655440007', x: 0, y: 390 })
] as const;
