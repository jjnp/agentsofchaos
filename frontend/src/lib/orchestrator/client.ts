import { parse } from 'valibot';

import {
	explainFileResponseSchema,
	orchestratorStateSchema,
	type ExplainFileResponse,
	type ExplainMode,
	type OrchestratorState
} from './contracts';

const orchestratorApiBasePath = '/api/orchestrator';

async function readJson<T>(response: Response): Promise<T> {
	if (!response.ok) {
		throw new Error(`Request failed with status ${response.status}`);
	}

	return (await response.json()) as T;
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
	const response = await fetch(`${orchestratorApiBasePath}${path}`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body)
	});

	return readJson<T>(response);
}

export async function fetchOrchestratorState(): Promise<OrchestratorState> {
	const response = await fetch(`${orchestratorApiBasePath}/state`);
	return parse(orchestratorStateSchema, await readJson(response));
}

export async function createRootInstance(): Promise<{ slot: number; label: string; agentUuid: string }> {
	return postJson('/instances');
}

export async function promptInstance(slot: number, message: string): Promise<void> {
	await postJson(`/instances/${slot}/prompt`, { message });
}

export async function forkInstance(
	slot: number
): Promise<{ sourceSlot: number; targetSlot: number; targetLabel: string }> {
	return postJson(`/instances/${slot}/fork`);
}

export async function stopInstance(slot: number): Promise<void> {
	await postJson(`/instances/${slot}/stop`);
}

export async function mergeInstances(
	sourceSlot: number,
	targetSlot: number
): Promise<{ sourceSlot: number; targetSlot: number; integrationSlot: number }> {
	return postJson('/merge', { sourceSlot, targetSlot });
}

export async function explainChangedFile(
	slot: number,
	filePath: string,
	mode: ExplainMode
): Promise<ExplainFileResponse> {
	return parse(
		explainFileResponseSchema,
		await postJson(`/instances/${slot}/explain-file`, { filePath, mode })
	);
}

export function connectToOrchestratorEvents(onEvent: (event: Record<string, unknown>) => void) {
	const source = new EventSource(`${orchestratorApiBasePath}/events/stream`);
	source.onmessage = (message) => {
		try {
			onEvent(JSON.parse(message.data) as Record<string, unknown>);
		} catch {
			// Ignore malformed buffered events.
		}
	};
	return source;
}
