import { describe, expect, it, vi } from 'vitest';

import {
	getOrchestratorEventStreamUrl,
	parseOrchestratorEvent,
	subscribeToOrchestratorEvents
} from './events';

class FakeEventSource {
	static latest: FakeEventSource | null = null;

	onopen: ((this: EventSource, ev: Event) => unknown) | null = null;
	onmessage: ((this: EventSource, ev: MessageEvent) => unknown) | null = null;
	onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
	readonly url: string;
	closed = false;

	constructor(url: string | URL) {
		this.url = String(url);
		FakeEventSource.latest = this;
	}

	close() {
		this.closed = true;
	}
}

describe('orchestrator event helpers', () => {
	it('builds the proxied sse url', () => {
		expect(getOrchestratorEventStreamUrl('/api/orchestrator/')).toBe(
			'/api/orchestrator/events/stream'
		);
	});

	it('parses typed orchestrator events', () => {
		const event = parseOrchestratorEvent({
			type: 'instance_created',
			slot: 0,
			label: 'pi-1',
			agentUuid: 'piagent_123'
		});

		expect(event.type).toBe('instance_created');
	});

	it('subscribes to sse events and emits parsed payloads', () => {
		const onEvent = vi.fn();
		const onStatusChange = vi.fn();
		const onError = vi.fn();
		const subscription = subscribeToOrchestratorEvents({
			baseUrl: '/api/orchestrator',
			onEvent,
			onStatusChange,
			onError,
			EventSourceCtor: FakeEventSource as unknown as typeof EventSource
		});

		expect(FakeEventSource.latest?.url).toBe('/api/orchestrator/events/stream');
		expect(onStatusChange).toHaveBeenCalledWith('connecting');

		FakeEventSource.latest?.onopen?.call(null as never, new Event('open'));
		expect(onStatusChange).toHaveBeenCalledWith('open');

		FakeEventSource.latest?.onmessage?.call(
			null as never,
			new MessageEvent('message', {
				data: JSON.stringify({
					type: 'session_output',
					slot: 0,
					label: 'pi-1',
					text: 'hello world'
				})
			})
		);
		expect(onEvent).toHaveBeenCalledWith(
			expect.objectContaining({ type: 'session_output', text: 'hello world' })
		);

		FakeEventSource.latest?.onerror?.call(null as never, new Event('error'));
		expect(onStatusChange).toHaveBeenCalledWith('error');
		expect(onError).toHaveBeenCalled();

		subscription.close();
		expect(FakeEventSource.latest?.closed).toBe(true);
		expect(onStatusChange).toHaveBeenCalledWith('closed');
	});
});
