<script lang="ts">
	import { tick } from 'svelte';

	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { CodeSnapshot, Run } from '$lib/orchestrator/contracts';

	import { nodeKindLabel, nodeStatusLabel } from '../agent-graph/node-styles';
	import NodeDiffViewer from '../node-diff/NodeDiffViewer.svelte';
	import ContextSnapshotView from './ContextSnapshotView.svelte';
	import MergeReport from './MergeReport.svelte';
	import TerminalOutput from './TerminalOutput.svelte';

	type DetailTab = 'events' | 'output' | 'changes' | 'context' | 'merge';

	interface Props {
		store: GraphStore;
	}

	let { store }: Props = $props();

	let eventViewport = $state<HTMLDivElement | null>(null);
	let activeTab = $state<DetailTab>('output');

	const node = $derived(store.selectedNode);
	const isMergeNode = $derived(node?.kind === 'merge');
	const originatingRun = $derived<Run | null>(
		node?.originating_run_id ? (store.runsById.get(node.originating_run_id) ?? null) : null
	);
	const codeSnapshot = $derived<CodeSnapshot | null>(
		node ? (store.codeSnapshotsById.get(node.code_snapshot_id) ?? null) : null
	);
	const recentEvents = $derived(store.events.slice(-200));

	$effect(() => {
		// If the user navigates away from a merge node while the merge tab is active,
		// fall back to output to keep the tab strip honest.
		if (activeTab === 'merge' && !isMergeNode) {
			activeTab = 'output';
		}
	});

	$effect(() => {
		if (!node) return;
		const snapshotId = node.code_snapshot_id;
		if (store.codeSnapshotsById.has(snapshotId)) return;
		void store.fetchCodeSnapshot(snapshotId).catch(() => {
			// Silently fall back to id; surfaced via store.lastError if it matters.
		});
	});

	$effect(() => {
		if (activeTab !== 'events') return;
		recentEvents;
		void tick().then(() => {
			if (eventViewport) {
				eventViewport.scrollTop = eventViewport.scrollHeight;
			}
		});
	});

	function formatTimestamp(value: string | undefined | null): string {
		if (!value) return '—';
		const isoZ = /[Zz]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`;
		return new Date(isoZ).toLocaleString();
	}

	function formatTime(value: string | undefined | null): string {
		const formatted = formatTimestamp(value);
		return formatted.split(', ').at(-1) ?? '';
	}

	function formatRelative(value: string | null): string {
		if (!value) return '';
		const isoZ = /[Zz]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`;
		const t = new Date(isoZ).getTime();
		const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000));
		if (diffSec < 60) return `${diffSec}s ago`;
		if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
		if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
		return `${Math.floor(diffSec / 86400)}d ago`;
	}
</script>

<aside class="inspector" aria-label="Selected node inspector">
	<header class="hd">
		<div class="hd-top">
			<p class="eyebrow">Agent node</p>
			{#if originatingRun?.status === 'running'}
				<span class="busy">running</span>
			{/if}
		</div>
		{#if node}
			<h1 class="title" title={node.title}>{node.title}</h1>
			<div class="meta-line">
				<span class="chip" data-kind={node.kind}>{nodeKindLabel(node.kind)}</span>
				<span class="chip status" data-status={node.status}>{nodeStatusLabel(node.status)}</span>
				{#if codeSnapshot}
					<code class="mono code-chip" title={codeSnapshot.commit_sha}>
						{codeSnapshot.commit_sha.slice(0, 8)}
					</code>
				{:else}
					<code class="mono dim">{node.id.slice(0, 8)}</code>
				{/if}
				<span class="dim">{formatRelative(node.created_at)}</span>
				{#if originatingRun}
					<span
						class="chip sandbox"
						data-sandbox={originatingRun.sandbox}
						title={`runtime: ${originatingRun.runtime} · sandbox: ${originatingRun.sandbox}`}
					>
						{originatingRun.runtime} / {originatingRun.sandbox}
					</span>
				{/if}
				{#if node.parent_node_ids.length > 0}
					<span class="lineage">
						←
						{#each node.parent_node_ids as parentId, i (parentId)}
							{#if i > 0}<span class="dim">,</span>{/if}
							<button
								type="button"
								class="link mono"
								title={parentId}
								onclick={() => store.select(parentId)}
							>
								{parentId.slice(0, 6)}
							</button>
						{/each}
					</span>
				{/if}
			</div>
		{:else}
			<h1 class="title dim">No node selected</h1>
			<p class="hint">Click a node on the canvas to inspect it.</p>
		{/if}
	</header>

	{#if store.lastError}
		<section class="error" role="alert">{store.lastError}</section>
	{/if}

	<section class="detail">
		<div class="tabs" role="tablist">
			<button
				type="button"
				class="tab"
				class:tab--active={activeTab === 'output'}
				role="tab"
				aria-selected={activeTab === 'output'}
				disabled={!node}
				onclick={() => (activeTab = 'output')}
			>
				Output
			</button>
			<button
				type="button"
				class="tab"
				class:tab--active={activeTab === 'changes'}
				role="tab"
				aria-selected={activeTab === 'changes'}
				disabled={!node}
				onclick={() => (activeTab = 'changes')}
			>
				Changes
			</button>
			<button
				type="button"
				class="tab"
				class:tab--active={activeTab === 'context'}
				role="tab"
				aria-selected={activeTab === 'context'}
				disabled={!node}
				onclick={() => (activeTab = 'context')}
			>
				Context
			</button>
			{#if isMergeNode}
				<button
					type="button"
					class="tab"
					class:tab--active={activeTab === 'merge'}
					role="tab"
					aria-selected={activeTab === 'merge'}
					onclick={() => (activeTab = 'merge')}
				>
					Merge
				</button>
			{/if}
			<button
				type="button"
				class="tab"
				class:tab--active={activeTab === 'events'}
				role="tab"
				aria-selected={activeTab === 'events'}
				onclick={() => (activeTab = 'events')}
			>
				Events
				<span class="badge-count">{store.events.length}</span>
			</button>
		</div>

		<div class="detail-body" role="tabpanel">
			{#if activeTab === 'events'}
				<div bind:this={eventViewport} class="terminal-viewport">
					{#if recentEvents.length === 0}
						<p class="terminal-empty">&gt; waiting for orchestrator events…</p>
					{:else}
						<ul class="terminal">
							{#each recentEvents as event (event.id)}
								<li>
									<time datetime={event.created_at}>{formatTime(event.created_at)}</time>
									<span class="topic" data-topic={event.topic}>{event.topic}</span>
								</li>
							{/each}
						</ul>
					{/if}
				</div>
			{:else if activeTab === 'output' && node}
				<TerminalOutput {store} {node} variant="full" />
			{:else if activeTab === 'changes' && node}
				<NodeDiffViewer {store} {node} />
			{:else if activeTab === 'context' && node}
				<ContextSnapshotView {store} {node} />
			{:else if activeTab === 'merge' && node && isMergeNode}
				<div class="merge-scroll">
					<MergeReport {store} {node} />
				</div>
			{/if}
		</div>
	</section>
</aside>

<style>
	.inspector {
		position: absolute;
		top: 1rem;
		left: 1rem;
		bottom: 1rem;
		z-index: 20;
		width: min(34rem, 40vw);
		display: grid;
		grid-template-rows: auto auto minmax(0, 1fr);
		gap: 0.55rem;
		padding: 0.85rem 0.95rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 1.4rem;
		background: rgb(18 19 15 / 0.9);
		backdrop-filter: blur(18px);
		box-shadow: var(--shadow-panel);
		overflow: hidden;
	}

	.hd {
		display: grid;
		gap: 0.3rem;
	}
	.hd-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.eyebrow {
		font-size: 0.62rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.busy {
		font-size: 0.6rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		padding: 0.18rem 0.55rem;
		border: 1px solid color-mix(in srgb, var(--color-warning) 50%, transparent);
		color: var(--color-warning);
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-warning) 12%, transparent);
		animation: pulse 1.4s ease-in-out infinite;
	}
	@keyframes pulse {
		50% {
			opacity: 0.6;
		}
	}
	.title {
		font-size: 1.05rem;
		font-weight: 600;
		color: var(--color-text);
		line-height: 1.25;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.title.dim {
		color: var(--color-text-muted);
		font-weight: 500;
	}
	.hint {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		margin: 0;
	}
	.meta-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.72rem;
		color: var(--color-text-muted);
	}
	.chip {
		padding: 0.1rem 0.55rem;
		border-radius: 999px;
		border: 1px solid var(--color-border);
		font-size: 0.62rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		background: color-mix(in srgb, var(--color-surface-elevated) 70%, transparent);
		color: var(--color-text-muted);
	}
	.chip[data-kind='root'] {
		color: var(--color-kind-root);
		border-color: color-mix(in srgb, var(--color-kind-root) 40%, var(--color-border));
	}
	.chip[data-kind='prompt'] {
		color: var(--color-kind-prompt);
		border-color: color-mix(in srgb, var(--color-kind-prompt) 40%, var(--color-border));
	}
	.chip[data-kind='merge'] {
		color: var(--color-kind-merge);
		border-color: color-mix(in srgb, var(--color-kind-merge) 40%, var(--color-border));
	}
	.chip[data-kind='fork'] {
		color: var(--color-kind-fork);
		border-color: color-mix(in srgb, var(--color-kind-fork) 40%, var(--color-border));
	}
	.chip.status[data-status='running'] {
		color: var(--color-warning);
		border-color: color-mix(in srgb, var(--color-warning) 40%, var(--color-border));
	}
	.chip.status[data-status='failed'],
	.chip.status[data-status='both_conflicted'] {
		color: var(--color-danger);
		border-color: color-mix(in srgb, var(--color-danger) 40%, var(--color-border));
	}
	.chip.status[data-status='code_conflicted'] {
		color: var(--color-status-code-conflicted);
		border-color: color-mix(in srgb, var(--color-status-code-conflicted) 40%, var(--color-border));
	}
	.chip.status[data-status='context_conflicted'] {
		color: var(--color-status-context-conflicted);
		border-color: color-mix(in srgb, var(--color-status-context-conflicted) 40%, var(--color-border));
	}
	.chip.sandbox {
		font-family: var(--font-mono);
		text-transform: lowercase;
		letter-spacing: 0;
		color: var(--color-text-muted);
	}
	/* Highlight non-`none` sandboxes — operators want at-a-glance
	   confirmation that the agent ran inside something. */
	.chip.sandbox[data-sandbox='bubblewrap'],
	.chip.sandbox[data-sandbox='docker'] {
		color: var(--color-primary);
		border-color: color-mix(in srgb, var(--color-primary) 40%, var(--color-border));
	}
	.code-chip {
		font-size: 0.7rem;
		color: var(--color-text);
	}
	.dim {
		color: var(--color-text-muted);
	}
	.lineage {
		display: inline-flex;
		gap: 0.2rem;
		align-items: center;
	}

	.error {
		padding: 0.55rem 0.8rem;
		border: 1px solid color-mix(in srgb, var(--color-danger) 38%, transparent);
		border-radius: 0.85rem;
		background: color-mix(in srgb, var(--color-danger) 10%, transparent);
		color: var(--color-danger);
		font-size: 0.78rem;
	}

	.detail {
		min-height: 0;
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 0.55rem;
		overflow: hidden;
	}
	.tabs {
		display: inline-flex;
		gap: 0.3rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 80%, black);
		padding: 0.25rem;
		border-radius: 999px;
		justify-self: start;
	}
	.tab {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		border: 0;
		background: transparent;
		color: var(--color-text-muted);
		padding: 0.4rem 0.75rem;
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		border-radius: 999px;
		cursor: pointer;
		transition:
			background-color 150ms ease,
			color 150ms ease;
	}
	.tab:hover:not(:disabled) {
		color: var(--color-text);
	}
	.tab:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.tab--active {
		background: color-mix(in srgb, var(--color-primary) 22%, rgb(18 19 15 / 1));
		color: var(--color-primary);
	}
	.badge-count {
		font-size: 0.6rem;
		font-family: var(--font-mono);
		padding: 0.05rem 0.4rem;
		background: color-mix(in srgb, var(--color-text-muted) 30%, transparent);
		border-radius: 999px;
		color: var(--color-text);
	}
	.detail-body {
		min-height: 0;
		overflow: hidden;
		display: grid;
	}
	.merge-scroll {
		min-height: 0;
		overflow: auto;
		padding-right: 0.25rem;
	}
	.terminal-viewport {
		min-height: 0;
		overflow: auto;
		padding: 0.65rem 0.75rem 0.4rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 1rem;
		background: rgb(12 13 10 / 0.45);
	}
	.terminal {
		display: flex;
		flex-direction: column;
		gap: 0.18rem;
		font-family: var(--font-mono);
		font-size: 0.74rem;
		color: #cfd7bc;
	}
	.terminal li {
		display: grid;
		grid-template-columns: 5rem 1fr;
		gap: 0.6rem;
	}
	.terminal time {
		color: var(--color-text-muted);
	}
	.topic[data-topic^='run_'] {
		color: var(--color-primary);
	}
	.topic[data-topic$='_node_created'] {
		color: var(--color-primary-accent);
	}
	.topic[data-topic='runtime_event'] {
		color: var(--color-text-muted);
	}
	.terminal-empty {
		font-family: var(--font-mono);
		font-size: 0.74rem;
		color: var(--color-text-muted);
	}

	.link {
		background: none;
		border: none;
		color: var(--color-primary-accent);
		cursor: pointer;
		padding: 0;
		font: inherit;
		text-align: left;
	}
	.link:hover {
		color: var(--color-text);
	}

	.mono {
		font-family: var(--font-mono);
	}

	@media (max-width: 1200px) {
		.inspector {
			width: min(30rem, calc(100vw - 5.5rem));
		}
	}
	@media (max-width: 900px) {
		.inspector {
			width: min(26rem, calc(100vw - 5.5rem));
		}
	}
	@media (max-width: 640px) {
		.inspector {
			top: 0.75rem;
			left: 0.75rem;
			right: 4.25rem;
			bottom: 0.75rem;
			width: auto;
		}
	}
</style>
