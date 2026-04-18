import * as v from 'valibot';

import { orchestratorEventSchema, type OrchestratorEvent } from './types';

const DEFAULT_BASE_PATH = '/api/orchestrator';

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

export type OrchestratorEventStreamStatus = 'connecting' | 'open' | 'error' | 'closed';

export type OrchestratorEventStreamOptions = Readonly<{
	baseUrl?: string;
	onEvent: (event: OrchestratorEvent) => void;
	onStatusChange?: (status: OrchestratorEventStreamStatus) => void;
	onError?: (error: Error) => void;
	EventSourceCtor?: typeof EventSource;
}>;

export type OrchestratorEventStreamSubscription = Readonly<{
	close: () => void;
}>;

export const getOrchestratorEventStreamUrl = (baseUrl: string = DEFAULT_BASE_PATH) =>
	`${trimTrailingSlash(baseUrl)}/events/stream`;

export const parseOrchestratorEvent = (payload: unknown) =>
	v.parse(orchestratorEventSchema, payload);

export const subscribeToOrchestratorEvents = ({
	baseUrl = DEFAULT_BASE_PATH,
	onEvent,
	onStatusChange,
	onError,
	EventSourceCtor = EventSource
}: OrchestratorEventStreamOptions): OrchestratorEventStreamSubscription => {
	onStatusChange?.('connecting');

	const eventSource = new EventSourceCtor(getOrchestratorEventStreamUrl(baseUrl));
	eventSource.onopen = () => {
		onStatusChange?.('open');
	};
	eventSource.onmessage = (message) => {
		try {
			onEvent(parseOrchestratorEvent(JSON.parse(message.data)));
		} catch (error) {
			onError?.(error instanceof Error ? error : new Error(String(error)));
		}
	};
	eventSource.onerror = () => {
		onStatusChange?.('error');
		onError?.(new Error('Failed to receive orchestrator events.'));
	};

	return {
		close: () => {
			eventSource.close();
			onStatusChange?.('closed');
		}
	};
};

export type { OrchestratorEvent };
