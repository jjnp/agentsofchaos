import { render } from 'vitest-browser-svelte';
import { describe, expect, it } from 'vitest';

import AgentCanvas from './AgentCanvas.svelte';
import { createAgentNode, createAgentNodePlacement } from '$lib/agent-graph/types';

describe('AgentCanvas', () => {
	it('renders nodes and parent connection lines', async () => {
		const rootNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440000',
			name: 'Root node'
		});
		const childNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440001',
			name: 'Child node',
			parentId: rootNode.id
		});

		const screen = await render(AgentCanvas, {
			nodes: [rootNode, childNode],
			placements: [
				createAgentNodePlacement({ nodeId: rootNode.id, x: 0, y: 0 }),
				createAgentNodePlacement({ nodeId: childNode.id, x: 180, y: 120 })
			],
			selectedNodeId: childNode.id
		});

		await expect.element(screen.getByText('Root node')).toBeInTheDocument();
		await expect.element(screen.getByText('Child node')).toBeInTheDocument();

		const connection = screen.container.querySelector('[data-connection-child-id]');
		expect(connection).not.toBeNull();
		expect(connection?.getAttribute('data-connection-child-id')).toBe(childNode.id);
	});
});
