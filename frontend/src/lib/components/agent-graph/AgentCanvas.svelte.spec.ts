import { render } from 'vitest-browser-svelte';
import { describe, expect, it } from 'vitest';

import AgentCanvas from './AgentCanvas.svelte';
import { createAgentNode, createAgentNodePlacement } from '$lib/agent-graph/types';

describe('AgentCanvas', () => {
	it('renders nodes and parent connection lines', async () => {
		const rootNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440000',
			name: 'Root node',
			status: 'running',
			details: {
				contextUsage: { tokens: 1400, percentage: 22 }
			}
		});
		const childNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440001',
			name: 'Child node',
			parentId: rootNode.id,
			status: 'completed',
			details: {
				contextUsage: { tokens: 640, percentage: 10 }
			}
		});

		const screen = await render(AgentCanvas, {
			nodes: [rootNode, childNode],
			placements: [
				createAgentNodePlacement({ nodeId: rootNode.id, x: 0, y: 0 }),
				createAgentNodePlacement({ nodeId: childNode.id, x: 180, y: 120 })
			],
			selectedNodeId: childNode.id
		});

		expect(screen.container.textContent).toContain('Root node');
		expect(screen.container.textContent).toContain('Child node');
		await expect.element(screen.getByText('Context 22%')).toBeInTheDocument();
		await expect.element(screen.getByText('Context 10%')).toBeInTheDocument();

		const connection = screen.container.querySelector('[data-connection-child-id]');
		expect(connection).not.toBeNull();
		expect(connection?.getAttribute('data-connection-child-id')).toBe(childNode.id);

		const runningSpinner = screen.container.querySelector(
			`[data-node-spinner-for="${rootNode.id}"]`
		);
		const completedSpinner = screen.container.querySelector(
			`[data-node-spinner-for="${childNode.id}"]`
		);
		expect(runningSpinner).not.toBeNull();
		expect(completedSpinner).toBeNull();
	});

	it('renders dashed merged-node connection lines with direction metadata', async () => {
		const sourceNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440010',
			name: 'Merged source',
			status: 'completed'
		});
		const targetNode = createAgentNode({
			id: '550e8400-e29b-41d4-a716-446655440011',
			name: 'Merged target',
			status: 'running',
			mergedNodes: [sourceNode.id]
		});

		const screen = await render(AgentCanvas, {
			nodes: [sourceNode, targetNode],
			placements: [
				createAgentNodePlacement({ nodeId: sourceNode.id, x: -140, y: 0 }),
				createAgentNodePlacement({ nodeId: targetNode.id, x: 140, y: 0 })
			],
			selectedNodeId: targetNode.id
		});

		const mergedConnection = screen.container.querySelector('[data-merged-source-node-id]');
		expect(mergedConnection).not.toBeNull();
		expect(mergedConnection?.getAttribute('data-merged-source-node-id')).toBe(sourceNode.id);
		expect(mergedConnection?.getAttribute('data-merged-target-node-id')).toBe(targetNode.id);
	});
});
