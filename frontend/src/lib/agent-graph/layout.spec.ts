import { describe, expect, it } from 'vitest';

import {
	clampScale,
	getCanvasTransform,
	getConnectionSegments,
	getNodeDepth,
	getViewportAfterZoom
} from './layout';
import { createAgentNode, createAgentNodePlacement } from './types';

const rootNode = createAgentNode({
	id: '550e8400-e29b-41d4-a716-446655440000',
	name: 'Root'
});

const childNode = createAgentNode({
	id: '550e8400-e29b-41d4-a716-446655440001',
	name: 'Child',
	parentId: rootNode.id
});

const placements = [
	createAgentNodePlacement({ nodeId: rootNode.id, x: 0, y: 0 }),
	createAgentNodePlacement({ nodeId: childNode.id, x: 120, y: 80 })
] as const;

describe('agent graph layout helpers', () => {
	it('returns connection segments for nodes with parents', () => {
		const segments = getConnectionSegments([rootNode, childNode], placements);

		expect(segments).toEqual([
			{
				childId: childNode.id,
				parentId: rootNode.id,
				x1: 0,
				y1: 0,
				x2: 120,
				y2: 80
			}
		]);
	});

	it('computes node depth from parent relationships', () => {
		expect(getNodeDepth(rootNode, [rootNode, childNode])).toBe(0);
		expect(getNodeDepth(childNode, [rootNode, childNode])).toBe(1);
	});

	it('clamps zoom levels and zooms around the cursor point', () => {
		const nextViewport = getViewportAfterZoom({
			viewport: { x: 100, y: 80, scale: 1 },
			deltaY: -200,
			pointer: { x: 300, y: 200 },
			minScale: 0.5,
			maxScale: 2.5
		});

		expect(nextViewport.scale).toBeGreaterThan(1);
		expect(clampScale(0.2, 0.5, 2.5)).toBe(0.5);
		expect(clampScale(3, 0.5, 2.5)).toBe(2.5);
	});

	it('builds an svg transform instead of css-scaling the entire viewport', () => {
		expect(getCanvasTransform({ x: 40, y: -20, scale: 1.5 }, { width: 900, height: 600 })).toBe(
			'translate(490 280) scale(1.5)'
		);
	});
});
