<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { ContextItem, ContextSnapshot, Node } from '$lib/orchestrator/contracts';

	interface Props {
		store: GraphStore;
		node: Node;
	}

	let { store, node }: Props = $props();

	let loading = $state(false);
	let error = $state<string | null>(null);

	const snapshot = $derived<ContextSnapshot | null>(
		store.contextSnapshotsById.get(node.context_snapshot_id) ?? null
	);

	$effect(() => {
		const target = node.context_snapshot_id;
		if (loading || store.contextSnapshotsById.has(target)) return;
		loading = true;
		error = null;
		void store
			.fetchContextSnapshot(target)
			.catch((err: unknown) => {
				error = err instanceof Error ? err.message : String(err);
			})
			.finally(() => {
				loading = false;
			});
	});

	type Section = {
		key: string;
		label: string;
		items: readonly ContextItem[];
	};

	const sections = $derived<Section[]>(
		snapshot
			? [
					{ key: 'goals', label: 'Goals', items: snapshot.goals },
					{ key: 'decisions', label: 'Decisions', items: snapshot.decisions },
					{ key: 'constraints', label: 'Constraints', items: snapshot.constraints },
					{ key: 'assumptions', label: 'Assumptions', items: snapshot.assumptions },
					{ key: 'open_questions', label: 'Open questions', items: snapshot.open_questions },
					{ key: 'todos', label: 'Todos', items: snapshot.todos },
					{ key: 'risks', label: 'Risks', items: snapshot.risks },
					{ key: 'handoff_notes', label: 'Handoff notes', items: snapshot.handoff_notes }
				]
			: []
	);

	const nonEmptySections = $derived(sections.filter((s) => s.items.length > 0));
	const fileCounts = $derived(
		snapshot
			? {
					read: snapshot.read_files.length,
					touched: snapshot.touched_files.length,
					symbols: snapshot.symbols.length
				}
			: null
	);
</script>

<section class="ctx">
	{#if loading && !snapshot}
		<p class="muted small">Loading context snapshot…</p>
	{:else if error}
		<p class="error small">{error}</p>
	{:else if snapshot}
		{#if snapshot.summary}
			<section class="summary">
				<p class="label">Summary</p>
				<pre class="summary-text">{snapshot.summary}</pre>
			</section>
		{/if}

		{#if fileCounts}
			<section class="filebar">
				<div class="chip">
					<span class="num">{fileCounts.read}</span>
					<span class="cap">read</span>
				</div>
				<div class="chip">
					<span class="num">{fileCounts.touched}</span>
					<span class="cap">touched</span>
				</div>
				<div class="chip">
					<span class="num">{fileCounts.symbols}</span>
					<span class="cap">symbols</span>
				</div>
			</section>
		{/if}

		{#if nonEmptySections.length === 0}
			<p class="muted small">
				The context snapshot is empty for this node. Pre-1.0 context projection only fills the
				summary + a basic goal item.
			</p>
		{:else}
			{#each nonEmptySections as section (section.key)}
				<section class="section">
					<p class="label">{section.label}</p>
					<ul>
						{#each section.items as item (item.id)}
							<li class:conflicted={item.status === 'conflicted'}>
								<span class="text">{item.text}</span>
								{#if item.status !== 'active'}
									<span class="status" data-status={item.status}>{item.status}</span>
								{/if}
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		{/if}

		{#if snapshot.touched_files.length > 0}
			<section class="section">
				<p class="label">Touched files</p>
				<ul class="paths">
					{#each snapshot.touched_files as ref (ref.path)}
						<li class="mono">{ref.path}</li>
					{/each}
				</ul>
			</section>
		{/if}
	{:else}
		<p class="muted small">No context snapshot loaded.</p>
	{/if}
</section>

<style>
	.ctx {
		display: grid;
		gap: 0.7rem;
		min-height: 0;
		overflow: auto;
		padding-right: 0.25rem;
	}
	.label {
		font-size: 0.68rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.summary {
		display: grid;
		gap: 0.35rem;
		padding: 0.65rem 0.85rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 1rem;
		background: rgb(12 13 10 / 0.78);
	}
	.summary-text {
		font: inherit;
		font-size: 0.78rem;
		line-height: 1.55;
		color: var(--color-text);
		white-space: pre-wrap;
		word-break: break-word;
		margin: 0;
		max-height: 12rem;
		overflow: auto;
	}
	.filebar {
		display: flex;
		gap: 0.5rem;
	}
	.chip {
		display: grid;
		justify-items: center;
		min-width: 3.4rem;
		padding: 0.3rem 0.55rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 0.7rem;
		background: color-mix(in srgb, var(--color-surface-elevated) 80%, black);
	}
	.num {
		font-family: var(--font-mono);
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text);
	}
	.cap {
		font-size: 0.6rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.section {
		display: grid;
		gap: 0.35rem;
	}
	.section ul {
		display: grid;
		gap: 0.3rem;
	}
	.section li {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.6rem;
		padding: 0.4rem 0.6rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 0.7rem;
		background: rgb(12 13 10 / 0.6);
		font-size: 0.78rem;
		line-height: 1.45;
	}
	.section li .text {
		color: var(--color-text);
		word-break: break-word;
	}
	.section li.conflicted {
		border-color: color-mix(in srgb, var(--color-danger) 38%, var(--color-border));
		background: color-mix(in srgb, var(--color-danger) 10%, transparent);
	}
	.status {
		font-size: 0.6rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.status[data-status='conflicted'] {
		color: var(--color-danger);
	}
	.paths {
		display: grid;
		gap: 0.2rem;
	}
	.paths li {
		font-size: 0.72rem;
		color: var(--color-text-muted);
	}
	.muted {
		color: var(--color-text-muted);
	}
	.small {
		font-size: 0.78rem;
	}
	.error {
		color: var(--color-danger);
	}
	.mono {
		font-family: var(--font-mono);
	}
</style>
