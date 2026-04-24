<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { MergeResponse, Node } from '$lib/orchestrator/contracts';

	interface Props {
		store: GraphStore;
		node: Node;
	}

	let { store, node }: Props = $props();

	const result = $derived<MergeResponse | null>(store.mergeResultsByNodeId.get(node.id) ?? null);
	const report = $derived(store.mergeReportsByNodeId.get(node.id) ?? null);

	let loading = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		const target = node.id;
		if (store.mergeReportsByNodeId.has(target) || loading) {
			return;
		}
		loading = true;
		error = null;
		void store
			.fetchMergeReport(target)
			.catch((err: unknown) => {
				error = err instanceof Error ? err.message : String(err);
			})
			.finally(() => {
				loading = false;
			});
	});

	const codeConflictCount = $derived(result?.code_conflicts.length ?? 0);
	const contextConflictCount = $derived(result?.context_conflicts.length ?? 0);
</script>

<section class="merge-report">
	<h3>Merge outcome</h3>
	{#if result}
		<dl class="kv">
			<dt>ancestor</dt>
			<dd>
				<button
					type="button"
					class="link mono"
					onclick={() => store.select(result.ancestor_node_id)}
				>
					{result.ancestor_node_id.slice(0, 8)}…
				</button>
			</dd>
			<dt>code conflicts</dt>
			<dd>{codeConflictCount}</dd>
			<dt>context conflicts</dt>
			<dd>{contextConflictCount}</dd>
			<dt>report</dt>
			<dd class="mono path">{result.report_path}</dd>
		</dl>

		{#if codeConflictCount > 0}
			<div class="block">
				<p class="label">Conflicted files</p>
				<ul class="files">
					{#each result.code_conflicts as path (path)}
						<li class="mono">{path}</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if contextConflictCount > 0}
			<div class="block">
				<p class="label">Context conflicts</p>
				<ul class="files">
					{#each result.context_conflicts as conflict, i (i)}
						<li class="mono">
							{(conflict['section'] as string | undefined) ?? 'unknown'}
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	{:else}
		<p class="muted small">No merge metadata cached for this node yet.</p>
	{/if}

	{#if loading}
		<p class="muted small">Loading merge report…</p>
	{:else if error}
		<p class="error small">{error}</p>
	{:else if report}
		<details class="raw">
			<summary>Raw report JSON</summary>
			<pre>{JSON.stringify(report.report, null, 2)}</pre>
		</details>
	{/if}
</section>

<style>
	.merge-report {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	h3 {
		font-size: 0.7rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.kv {
		display: grid;
		grid-template-columns: max-content 1fr;
		column-gap: 1rem;
		row-gap: 0.35rem;
		font-size: 0.8rem;
	}
	.kv dt {
		color: var(--color-text-muted);
		text-transform: lowercase;
	}
	.kv dd {
		margin: 0;
		color: var(--color-text);
		word-break: break-all;
	}
	.path {
		font-size: 0.7rem;
	}
	.block {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.label {
		font-size: 0.7rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.files {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.8rem;
	}
	.link {
		background: none;
		border: none;
		padding: 0;
		color: var(--color-primary-accent);
		cursor: pointer;
		text-align: left;
	}
	.muted {
		color: var(--color-text-muted);
	}
	.small {
		font-size: 0.75rem;
	}
	.error {
		color: var(--color-danger);
	}
	.raw summary {
		cursor: pointer;
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}
	.raw pre {
		font-size: 0.7rem;
		max-height: 16rem;
		overflow: auto;
		padding: 0.5rem;
		background: var(--color-surface-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		margin-top: 0.5rem;
	}
</style>
