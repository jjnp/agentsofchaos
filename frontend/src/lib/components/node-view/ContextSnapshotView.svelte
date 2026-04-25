<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type {
		ContextDiff,
		ContextItem,
		ContextItemDiff,
		ContextSectionDiff,
		ContextSnapshot,
		Node
	} from '$lib/orchestrator/contracts';

	interface Props {
		store: GraphStore;
		node: Node;
	}

	let { store, node }: Props = $props();

	let snapshotLoading = $state(false);
	let snapshotError = $state<string | null>(null);
	let diffLoading = $state(false);
	let diffError = $state<string | null>(null);
	let mode = $state<'diff' | 'full'>('diff');

	// Reset mode when the inspected node changes — root nodes have no base
	// snapshot to diff against, so they default to full view.
	$effect(() => {
		mode = node.parent_node_ids.length > 0 ? 'diff' : 'full';
	});

	const snapshot = $derived<ContextSnapshot | null>(
		store.contextSnapshotsById.get(node.context_snapshot_id) ?? null
	);
	const diff = $derived<ContextDiff | null>(store.contextDiffsByNodeId.get(node.id) ?? null);

	$effect(() => {
		const target = node.context_snapshot_id;
		if (snapshotLoading || store.contextSnapshotsById.has(target)) return;
		snapshotLoading = true;
		snapshotError = null;
		void store
			.fetchContextSnapshot(target)
			.catch((err: unknown) => {
				snapshotError = err instanceof Error ? err.message : String(err);
			})
			.finally(() => {
				snapshotLoading = false;
			});
	});

	$effect(() => {
		// Skip the diff fetch for root nodes — there's no base to diff against.
		if (mode !== 'diff' || node.parent_node_ids.length === 0) return;
		const target = node.id;
		if (diffLoading || store.contextDiffsByNodeId.has(target)) return;
		diffLoading = true;
		diffError = null;
		void store
			.fetchContextDiff(target)
			.catch((err: unknown) => {
				diffError = err instanceof Error ? err.message : String(err);
			})
			.finally(() => {
				diffLoading = false;
			});
	});

	type SnapshotSection = {
		key: string;
		label: string;
		items: readonly ContextItem[];
	};

	const snapshotSections = $derived<SnapshotSection[]>(
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

	const nonEmptySections = $derived(snapshotSections.filter((s) => s.items.length > 0));
	const fileCounts = $derived(
		snapshot
			? {
					read: snapshot.read_files.length,
					touched: snapshot.touched_files.length,
					symbols: snapshot.symbols.length
				}
			: null
	);

	const sectionLabels: Record<string, string> = {
		goals: 'Goals',
		decisions: 'Decisions',
		constraints: 'Constraints',
		assumptions: 'Assumptions',
		open_questions: 'Open questions',
		todos: 'Todos',
		risks: 'Risks',
		handoff_notes: 'Handoff notes'
	};

	const nonEmptyDiffSections = $derived<ContextSectionDiff[]>(
		diff ? diff.sections.filter((s) => s.items.length > 0) : []
	);
</script>

<section class="ctx">
	{#if node.parent_node_ids.length > 0}
		<div class="mode-toggle" role="radiogroup" aria-label="Context view mode">
			<button
				type="button"
				class="seg"
				class:active={mode === 'diff'}
				onclick={() => (mode = 'diff')}
				role="radio"
				aria-checked={mode === 'diff'}
			>
				Diff
			</button>
			<button
				type="button"
				class="seg"
				class:active={mode === 'full'}
				onclick={() => (mode = 'full')}
				role="radio"
				aria-checked={mode === 'full'}
			>
				Full
			</button>
		</div>
	{/if}

	{#if mode === 'diff'}
		{#if diffLoading && !diff}
			<p class="muted small">Loading context diff…</p>
		{:else if diffError}
			<p class="error small">{diffError}</p>
		{:else if diff}
			<dl class="kv">
				<dt>added</dt>
				<dd class="num add">{diff.totals.additions}</dd>
				<dt>removed</dt>
				<dd class="num remove">{diff.totals.removals}</dd>
				<dt>changed</dt>
				<dd class="num change">{diff.totals.changes}</dd>
			</dl>
			{#if nonEmptyDiffSections.length === 0}
				<p class="muted small">No context changes against the parent snapshot.</p>
			{:else}
				{#each nonEmptyDiffSections as section (section.section)}
					<section class="section">
						<p class="label">
							{sectionLabels[section.section] ?? section.section}
							<span class="counters">
								{#if section.additions > 0}<span class="add">+{section.additions}</span>{/if}
								{#if section.removals > 0}<span class="remove">−{section.removals}</span>{/if}
								{#if section.changes > 0}<span class="change">~{section.changes}</span>{/if}
							</span>
						</p>
						<ul>
							{#each section.items as item (item.item_id)}
								<li class="diff-row" data-change={item.change_type}>
									{@render diffItemRow(item)}
								</li>
							{/each}
						</ul>
					</section>
				{/each}
			{/if}
		{:else}
			<p class="muted small">No context diff loaded.</p>
		{/if}
	{:else if snapshotLoading && !snapshot}
		<p class="muted small">Loading context snapshot…</p>
	{:else if snapshotError}
		<p class="error small">{snapshotError}</p>
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
					<span class="num-big">{fileCounts.read}</span>
					<span class="cap">read</span>
				</div>
				<div class="chip">
					<span class="num-big">{fileCounts.touched}</span>
					<span class="cap">touched</span>
				</div>
				<div class="chip">
					<span class="num-big">{fileCounts.symbols}</span>
					<span class="cap">symbols</span>
				</div>
			</section>
		{/if}

		{#if nonEmptySections.length === 0}
			<p class="muted small">The context snapshot is empty for this node.</p>
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

{#snippet diffItemRow(item: ContextItemDiff)}
	{#if item.change_type === 'added'}
		<div class="row-head">
			<span class="badge add">added</span>
		</div>
		<p class="text">{item.after?.text ?? ''}</p>
	{:else if item.change_type === 'removed'}
		<div class="row-head">
			<span class="badge remove">removed</span>
		</div>
		<p class="text strike">{item.before?.text ?? ''}</p>
	{:else}
		<div class="row-head">
			<span class="badge change">changed</span>
		</div>
		<div class="side-by-side">
			<div class="side">
				<p class="side-label">before</p>
				<p class="side-text strike">{item.before?.text ?? ''}</p>
			</div>
			<div class="side">
				<p class="side-label">after</p>
				<p class="side-text">{item.after?.text ?? ''}</p>
			</div>
		</div>
	{/if}
{/snippet}

<style>
	.ctx {
		display: grid;
		gap: 0.7rem;
		min-height: 0;
		overflow: auto;
		padding-right: 0.25rem;
	}
	.mode-toggle {
		display: inline-flex;
		gap: 0;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 0.7rem;
		overflow: hidden;
		width: max-content;
	}
	.seg {
		background: transparent;
		color: var(--color-text-muted);
		border: none;
		padding: 0.3rem 0.7rem;
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
	}
	.seg.active {
		background: color-mix(in srgb, var(--color-primary) 18%, transparent);
		color: var(--color-primary);
	}
	.label {
		font-size: 0.68rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.counters {
		display: inline-flex;
		gap: 0.45rem;
		text-transform: none;
		letter-spacing: normal;
		font-family: var(--font-mono);
		font-size: 0.68rem;
	}
	.kv {
		display: flex;
		gap: 1rem;
		font-size: 0.78rem;
	}
	.kv dt {
		color: var(--color-text-muted);
		text-transform: lowercase;
		margin: 0;
	}
	.kv dd {
		margin: 0;
		font-family: var(--font-mono);
	}
	.num {
		font-family: var(--font-mono);
	}
	.add {
		color: var(--color-success, #5eb98c);
	}
	.remove {
		color: var(--color-danger);
	}
	.change {
		color: var(--color-primary);
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
	.num-big {
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
		list-style: none;
		padding: 0;
		margin: 0;
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
	.diff-row {
		flex-direction: column;
		align-items: stretch;
		gap: 0.3rem;
	}
	.diff-row[data-change='added'] {
		border-color: color-mix(in srgb, var(--color-success, #5eb98c) 36%, var(--color-border));
		background: color-mix(in srgb, var(--color-success, #5eb98c) 10%, transparent);
	}
	.diff-row[data-change='removed'] {
		border-color: color-mix(in srgb, var(--color-danger) 36%, var(--color-border));
		background: color-mix(in srgb, var(--color-danger) 8%, transparent);
	}
	.diff-row[data-change='changed'] {
		border-color: color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 6%, transparent);
	}
	.row-head {
		display: flex;
		justify-content: flex-start;
	}
	.badge {
		font-size: 0.6rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		padding: 0.1rem 0.4rem;
		border-radius: 0.4rem;
		border: 1px solid currentColor;
	}
	.text {
		margin: 0;
		color: var(--color-text);
		word-break: break-word;
	}
	.strike {
		text-decoration: line-through;
		text-decoration-color: color-mix(in srgb, var(--color-danger) 60%, transparent);
		color: color-mix(in srgb, var(--color-text) 70%, transparent);
	}
	.side-by-side {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.4rem;
	}
	.side {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.side-label {
		font-size: 0.6rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--color-text-muted);
		margin: 0;
	}
	.side-text {
		margin: 0;
		font-size: 0.74rem;
		padding: 0.35rem 0.45rem;
		background: var(--color-surface-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.4rem;
		white-space: pre-wrap;
		word-break: break-word;
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
	.status[data-status='resolved'] {
		color: var(--color-primary);
	}
	.paths {
		display: grid;
		gap: 0.2rem;
		list-style: none;
		padding: 0;
		margin: 0;
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
