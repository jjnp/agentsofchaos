import { describe, expect, it, vi } from 'vitest';

import { createOrchestratorClient } from './client';

describe('createOrchestratorClient', () => {
	it('requests state through the configured base url', async () => {
		const fetchMock = vi.fn(
			async () =>
				new Response(
					JSON.stringify({
						sessionId: 'b49645d87d60',
						model: 'openai/gpt-5.4-mini',
						mergeModel: 'gpt-5.4-mini',
						instanceCount: 0,
						instances: []
					}),
					{ status: 200 }
				)
		);
		const client = createOrchestratorClient({
			baseUrl: '/api/orchestrator',
			fetch: fetchMock as typeof fetch
		});

		const state = await client.getState();

		expect(fetchMock).toHaveBeenCalledWith('/api/orchestrator/state', expect.any(Object));
		expect(state.instanceCount).toBe(0);
	});

	it('posts prompt requests as json', async () => {
		const fetchMock = vi.fn(
			async () =>
				new Response(JSON.stringify({ accepted: true, slot: 2, queuedAt: 1776514597202 }), {
					status: 202
				})
		);
		const client = createOrchestratorClient({ fetch: fetchMock as typeof fetch });

		await client.promptInstance(2, 'Implement feature X');

		expect(fetchMock).toHaveBeenCalledWith('/api/orchestrator/instances/2/prompt', {
			body: JSON.stringify({ message: 'Implement feature X' }),
			headers: expect.any(Headers),
			method: 'POST'
		});
	});

	it('throws typed api errors', async () => {
		const fetchMock = vi.fn(
			async () =>
				new Response(
					JSON.stringify({
						error: {
							code: 'INVALID_SLOT',
							message: 'Invalid slot: 9'
						}
					}),
					{ status: 404 }
				)
		);
		const client = createOrchestratorClient({ fetch: fetchMock as typeof fetch });

		await expect(client.getInstance(9)).rejects.toMatchObject({
			name: 'OrchestratorApiError',
			status: 404,
			code: 'INVALID_SLOT',
			message: 'Invalid slot: 9'
		});
	});
});
