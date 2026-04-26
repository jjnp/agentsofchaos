<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { ContextSnapshot, Node, NodeDiff } from '$lib/orchestrator/contracts';

	import DiffFileList from './DiffFileList.svelte';
	import DiffFileView from './DiffFileView.svelte';
	import DiffSummaryCard from './DiffSummaryCard.svelte';

	interface Props {
		store: GraphStore;
		node: Node;
	}

	let { store, node }: Props = $props();

	let loading = $state(false);
	let error = $state<string | null>(null);
	let selectedPath = $state<string | null>(null);

	const diff = $derived<NodeDiff | null>(store.diffsByNodeId.get(node.id) ?? null);
	const contextSnapshot = $derived<ContextSnapshot | null>(
		store.contextSnapshotsById.get(node.context_snapshot_id) ?? null
	);
	const selectedFile = $derived(
		diff?.files.find((file) => file.path === selectedPath) ?? null
	);

	$effect(() => {
		const targetNodeId = node.id;
		if (loading) return;
		if (store.diffsByNodeId.has(targetNodeId)) return;
		loading = true;
		error = null;
		void store
			.fetchNodeDiff(targetNodeId)
			.catch((err: unknown) => {
				error = err instanceof Error ? err.message : String(err);
			})
			.finally(() => {
				loading = false;
			});
	});

	// Pull the context snapshot too — its `summary` field gives the
	// `DiffSummaryCard` a body that's actually informational ("Done —
	// created tictactoe.js…") instead of a duplicate of the +/- chip
	// row directly below.
	$effect(() => {
		const id = node.context_snapshot_id;
		if (store.contextSnapshotsById.has(id)) return;
		void store.fetchContextSnapshot(id).catch(() => {
			// Surfaced via store.lastError elsewhere if it actually matters.
		});
	});

	$effect(() => {
		if (!diff) return;
		if (selectedPath && diff.files.some((file) => file.path === selectedPath)) return;
		selectedPath = diff.files[0]?.path ?? null;
	});

	async function refresh() {
		loading = true;
		error = null;
		try {
			await store.fetchNodeDiff(node.id, { force: true });
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	const cardTitle = 'Changes';
	const cardSourceLabel = $derived<string | null>(
		diff
			? `${diff.base_commit_sha ? diff.base_commit_sha.slice(0, 12) : 'empty tree'} → ${diff.head_commit_sha.slice(0, 12)}`
			: null
	);
	const cardBody = $derived(() => {
		// Priority order:
		//   1. First non-heading line of the run's summary — gives the
		//      card a real "what did this run do" sentence.
		//   2. Node title — for nodes without a meaningful summary.
		//   3. The file-stat sentence — last-resort fallback that
		//      duplicates the chips below but at least says something.
		const summary = contextSnapshot?.summary ?? '';
		const firstLine = summary
			.split('\n')
			.map((line) => line.trim())
			.find((line) => line.length > 0 && !line.startsWith('#'));
		if (firstLine) return firstLine;
		if (node.title) return node.title;
		if (!diff) return 'Diff not loaded.';
		const { files, additions, deletions } = diff.totals;
		if (files === 0) return 'No changes between this node and its parent.';
		const fileLabel = files === 1 ? 'file' : 'files';
		return `${files} ${fileLabel} changed — +${additions}, -${deletions}`;
	});
</script>

<section class="viewer">
	<DiffSummaryCard
		title={cardTitle}
		body={cardBody()}
		sourceLabel={cardSourceLabel}
		loading={loading && !diff}
		error={null}
	/>

	<div class="totals-bar">
		<div class="totals-grid">
			<div class="stat">
				<span class="num">{diff?.totals.files ?? 0}</span>
				<span class="cap">files</span>
			</div>
			<div class="stat add">
				<span class="num">+{diff?.totals.additions ?? 0}</span>
				<span class="cap">added</span>
			</div>
			<div class="stat del">
				<span class="num">-{diff?.totals.deletions ?? 0}</span>
				<span class="cap">removed</span>
			</div>
		</div>
		<button type="button" class="refresh" onclick={refresh} disabled={loading}>
			{loading ? 'Loading…' : 'Refresh diff'}
		</button>
	</div>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	{#if loading && !diff}
		<p class="loading">Loading diff…</p>
	{:else if diff && diff.files.length === 0}
		<p class="empty">No changes between this node and its parent.</p>
	{:else if diff}
		<div class="split">
			<DiffFileList files={diff.files} {selectedPath} onSelect={(path) => (selectedPath = path)} />
			<DiffFileView file={selectedFile} />
		</div>
	{/if}
</section>

<style>
	.viewer {
		display: grid;
		grid-template-rows: auto auto minmax(0, 1fr);
		gap: 0.6rem;
		min-height: 0;
	}
	.totals-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.6rem;
	}
	.totals-grid {
		display: flex;
		gap: 0.45rem;
		align-items: center;
	}
	.stat {
		display: grid;
		justify-items: center;
		min-width: 3.4rem;
		padding: 0.3rem 0.55rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 0.7rem;
		background: color-mix(in srgb, var(--color-surface-elevated) 80%, black);
	}
	.stat .num {
		font-family: var(--font-mono);
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text);
	}
	.stat .cap {
		font-size: 0.6rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.stat.add .num {
		color: var(--color-success);
	}
	.stat.del .num {
		color: var(--color-danger);
	}
	.refresh {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 80%, black);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.5rem 0.8rem;
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
	}
	.refresh:hover:not(:disabled) {
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
		color: var(--color-primary);
	}
	.refresh:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.error {
		color: var(--color-danger);
		font-size: 0.78rem;
	}
	.loading,
	.empty {
		color: var(--color-text-muted);
		font-size: 0.78rem;
	}
	.split {
		display: grid;
		grid-template-columns: minmax(10rem, 14rem) minmax(0, 1fr);
		gap: 0.6rem;
		min-height: 0;
		overflow: hidden;
	}
	@media (max-width: 1100px) {
		.split {
			grid-template-columns: 1fr;
		}
	}
</style>
