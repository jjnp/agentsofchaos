<script lang="ts">
	import { tick } from 'svelte';

	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { Node, Run } from '$lib/orchestrator/contracts';

	interface Props {
		store: GraphStore;
		node: Node;
		variant?: 'compact' | 'full';
	}

	let { store, node, variant = 'compact' }: Props = $props();

	let scrollEl = $state<HTMLDivElement | null>(null);

	const originatingRun = $derived<Run | null>(
		node.originating_run_id ? (store.runsById.get(node.originating_run_id) ?? null) : null
	);
	const isLive = $derived(originatingRun?.status === 'running');

	type TerminalLine = { id: string; tone: 'info' | 'mock' | 'error'; text: string };

	const MOCK_LINES: readonly TerminalLine[] = [
		{ id: 'mock-1', tone: 'mock', text: '$ pi run --resume node-7e2f' },
		{ id: 'mock-2', tone: 'mock', text: '✓ workspace materialized at /workspace' },
		{ id: 'mock-3', tone: 'mock', text: '✓ context snapshot loaded (12 items)' },
		{ id: 'mock-4', tone: 'mock', text: '› reading src/lib/agent-graph/layout.ts' },
		{ id: 'mock-5', tone: 'mock', text: '› drafting refactor plan…' },
		{ id: 'mock-6', tone: 'mock', text: '✎ edit: extract ring placement helper' },
		{ id: 'mock-7', tone: 'mock', text: '⏵ waiting for live output (mock)' }
	];

	const liveLines = $derived.by<TerminalLine[]>(() => {
		if (!originatingRun) return [];
		const runId = originatingRun.id;
		const out: TerminalLine[] = [];
		for (const event of store.events) {
			if (event.topic !== 'runtime_event') continue;
			if (event.payload['run_id'] !== runId) continue;
			const runtime = event.payload['runtime_event'];
			if (!runtime || typeof runtime !== 'object') continue;
			const r = runtime as Record<string, unknown>;
			const kind = typeof r['kind'] === 'string' ? (r['kind'] as string) : '';
			const lifecycleMessage = typeof r['message'] === 'string' ? (r['message'] as string) : '';

			// Pull the actual assistant/user text out of pi message_end events.
			if (kind === 'runtime.message_end') {
				const errorText = extractMessageError(r);
				if (errorText) {
					out.push({ id: `${event.id}-err`, tone: 'error', text: errorText });
					continue;
				}
				const text = extractMessageText(r);
				if (text) {
					out.push({ id: `${event.id}-msg`, tone: 'info', text });
					continue;
				}
			}
			// Skip noisy paired markers in favour of richer ones.
			if (
				kind === 'runtime.message_start' ||
				kind === 'runtime.turn_start' ||
				kind === 'runtime.turn_end'
			) {
				continue;
			}
			if (lifecycleMessage) {
				out.push({ id: event.id, tone: 'info', text: `· ${lifecycleMessage}` });
			}
		}
		return out;
	});

	function extractMessageError(runtime: Record<string, unknown>): string | null {
		const payload = runtime['payload'];
		if (!payload || typeof payload !== 'object') return null;
		const piEvent = (payload as Record<string, unknown>)['piEvent'];
		if (!piEvent || typeof piEvent !== 'object') return null;
		const message = (piEvent as Record<string, unknown>)['message'];
		if (!message || typeof message !== 'object') return null;
		const stopReason = (message as Record<string, unknown>)['stopReason'];
		const errorMessage = (message as Record<string, unknown>)['errorMessage'];
		if (stopReason === 'error' && typeof errorMessage === 'string' && errorMessage.length > 0) {
			const model =
				typeof (message as Record<string, unknown>)['model'] === 'string'
					? ` [${(message as Record<string, unknown>)['model']}]`
					: '';
			return `⚠ ${errorMessage}${model}`;
		}
		return null;
	}

	function extractMessageText(runtime: Record<string, unknown>): string | null {
		const payload = runtime['payload'];
		if (!payload || typeof payload !== 'object') return null;
		const piEvent = (payload as Record<string, unknown>)['piEvent'];
		if (!piEvent || typeof piEvent !== 'object') return null;
		const message = (piEvent as Record<string, unknown>)['message'];
		if (!message || typeof message !== 'object') return null;
		const role = (message as Record<string, unknown>)['role'];
		const content = (message as Record<string, unknown>)['content'];
		if (!Array.isArray(content)) return null;
		const texts: string[] = [];
		for (const part of content) {
			if (
				part &&
				typeof part === 'object' &&
				(part as { type?: unknown }).type === 'text' &&
				typeof (part as { text?: unknown }).text === 'string'
			) {
				texts.push((part as { text: string }).text);
			}
		}
		const joined = texts.join('\n').trim();
		if (!joined) return null;
		const prefix = role === 'assistant' ? '🤖 ' : role === 'user' ? '👤 ' : '';
		return `${prefix}${joined}`;
	}

	const lines = $derived<readonly TerminalLine[]>(
		liveLines.length > 0 ? liveLines : MOCK_LINES
	);
	const showingMock = $derived(liveLines.length === 0);

	$effect(() => {
		lines;
		void tick().then(() => {
			if (scrollEl) {
				scrollEl.scrollTop = scrollEl.scrollHeight;
			}
		});
	});
</script>

<section class="terminal terminal--{variant}" aria-label="Live runtime output">
	<header class="head">
		<span class="dot" data-active={isLive}></span>
		<span class="label">live output</span>
		{#if showingMock}
			<span class="tag">mock</span>
		{:else}
			<span class="tag tag--live">{liveLines.length} lines</span>
		{/if}
	</header>
	<div bind:this={scrollEl} class="body">
		{#each lines as line (line.id)}
			<div class="line line--{line.tone}">{line.text}</div>
		{/each}
	</div>
</section>

<style>
	.terminal {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 0.3rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 0.85rem;
		background: rgb(8 9 7 / 0.92);
		padding: 0.45rem 0.55rem 0.5rem;
		min-height: 0;
	}
	.terminal--full {
		height: 100%;
	}
	.head {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.6rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.dot {
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-text-muted) 60%, transparent);
	}
	.dot[data-active='true'] {
		background: var(--color-success);
		box-shadow: 0 0 0.45rem color-mix(in srgb, var(--color-success) 60%, transparent);
		animation: term-pulse 1.4s ease-in-out infinite;
	}
	@keyframes term-pulse {
		50% {
			opacity: 0.5;
		}
	}
	.label {
		flex: 1;
	}
	.tag {
		padding: 0.05rem 0.45rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 999px;
		font-size: 0.55rem;
		letter-spacing: 0.14em;
		color: var(--color-text-muted);
	}
	.tag--live {
		color: var(--color-primary);
		border-color: color-mix(in srgb, var(--color-primary) 38%, var(--color-border));
	}
	.body {
		overflow: auto;
		font-family: var(--font-mono);
		font-size: 0.7rem;
		line-height: 1.5;
		color: #cfd7bc;
		min-height: 0;
	}
	.terminal--compact .body {
		max-height: 8.5rem;
	}
	.terminal--full .body {
		font-size: 0.78rem;
	}
	.line {
		white-space: pre-wrap;
		word-break: break-word;
	}
	.line--mock {
		color: color-mix(in srgb, var(--color-text-muted) 60%, var(--color-text));
		opacity: 0.65;
	}
	.line--info {
		color: #cfd7bc;
	}
	.line--error {
		color: var(--color-danger);
		background: color-mix(in srgb, var(--color-danger) 8%, transparent);
		padding: 0.1rem 0.35rem;
		border-radius: 0.4rem;
	}
</style>
