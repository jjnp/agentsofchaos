<script lang="ts">
	import * as v from 'valibot';

	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import {
		typedMergeReportSchema,
		type CodeConflictFile,
		type ContextConflict,
		type MergeResponse,
		type Node,
		type TypedMergeReport
	} from '$lib/orchestrator/contracts';

	interface Props {
		store: GraphStore;
		node: Node;
	}

	let { store, node }: Props = $props();

	const result = $derived<MergeResponse | null>(store.mergeResultsByNodeId.get(node.id) ?? null);
	const cachedReport = $derived(store.mergeReportsByNodeId.get(node.id) ?? null);

	let loading = $state(false);
	let error = $state<string | null>(null);
	let resolving = $state(false);
	let resolutionError = $state<string | null>(null);
	let resolutionPrompt = $state('');

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

	const typedReport = $derived<TypedMergeReport | null>(
		cachedReport ? safeParseTypedReport(cachedReport.report) : null
	);

	const isConflicted = $derived<boolean>(
		node.status === 'code_conflicted' ||
			node.status === 'context_conflicted' ||
			node.status === 'both_conflicted'
	);

	function safeParseTypedReport(raw: Record<string, unknown>): TypedMergeReport | null {
		const parsed = v.safeParse(typedMergeReportSchema, raw);
		return parsed.success ? parsed.output : null;
	}

	async function submitResolution(event: SubmitEvent) {
		event.preventDefault();
		const trimmed = resolutionPrompt.trim();
		if (!trimmed || resolving) return;
		resolving = true;
		resolutionError = null;
		try {
			await store.resolveMerge(node.id, trimmed);
			resolutionPrompt = '';
		} catch (err) {
			resolutionError = err instanceof Error ? err.message : String(err);
		} finally {
			resolving = false;
		}
	}
</script>

<section class="merge-report">
	<h3>Merge outcome</h3>

	{#if result}
		<dl class="kv">
			<dt>status</dt>
			<dd class="status status-{node.status}">{node.status.replace(/_/g, ' ')}</dd>
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
			<dt>code role</dt>
			<dd class="mono">{result.code_snapshot_role}</dd>
			<dt>context role</dt>
			<dd class="mono">{result.context_snapshot_role}</dd>
			{#if isConflicted}
				<dt>resolution policy</dt>
				<dd class="mono">{result.resolution_policy}</dd>
			{/if}
			<dt>report</dt>
			<dd class="mono path">{result.report_path}</dd>
		</dl>
	{:else}
		<p class="muted small">No merge metadata cached for this node yet.</p>
	{/if}

	{#if loading}
		<p class="muted small">Loading merge report…</p>
	{:else if error}
		<p class="error small">{error}</p>
	{/if}

	{#if typedReport}
		{@const codeMerge = typedReport.code_merge}
		{@const contextMerge = typedReport.context_merge}

		<div class="block">
			<p class="label">Code merge</p>
			{#if codeMerge.clean}
				<p class="muted small">Clean — no code conflicts.</p>
			{:else}
				<ul class="files">
					{#each codeMerge.conflict_details as detail (detail.path)}
						<li class="conflict-file">
							{@render codeConflictRow(detail)}
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<div class="block">
			<p class="label">Context merge</p>
			{#if contextMerge.conflict_count === 0}
				<p class="muted small">Clean — no context conflicts.</p>
			{:else}
				<ul class="files">
					{#each contextMerge.conflicts as conflict (conflict.item_id)}
						<li class="conflict-file">
							{@render contextConflictRow(conflict)}
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		{#if isConflicted}
			<div class="block">
				<p class="label">Agent-driven resolution</p>
				<form class="resolve-form" onsubmit={submitResolution}>
					<textarea
						class="textarea"
						rows="3"
						placeholder="Describe how to resolve these conflicts (the agent receives the merge report alongside this prompt)…"
						bind:value={resolutionPrompt}
						disabled={resolving}
					></textarea>
					<div class="resolve-actions">
						<span class="hint">A successor RESOLUTION node will be created.</span>
						<button
							type="submit"
							class="btn btn--primary"
							disabled={resolving || resolutionPrompt.trim().length === 0}
						>
							{resolving ? 'Sending…' : 'Resolve'}
						</button>
					</div>
					{#if resolutionError}
						<p class="error small">{resolutionError}</p>
					{/if}
				</form>
			</div>
		{/if}
	{:else if cachedReport && !loading}
		<details class="raw">
			<summary>Raw report JSON</summary>
			<pre>{JSON.stringify(cachedReport.report, null, 2)}</pre>
		</details>
	{/if}
</section>

{#snippet codeConflictRow(detail: CodeConflictFile)}
	<div class="conflict-head">
		<span class="mono">{detail.path}</span>
		<span class="muted small">{detail.marker_count} marker{detail.marker_count === 1 ? '' : 's'}</span>
	</div>
	{#if detail.preview}
		<pre class="preview">{detail.preview}</pre>
	{/if}
{/snippet}

{#snippet contextConflictRow(conflict: ContextConflict)}
	<div class="conflict-head">
		<span class="mono">{conflict.section}</span>
		<span class="muted small">item {conflict.item_id.slice(0, 8)}…</span>
	</div>
	<p class="explanation small">{conflict.explanation}</p>
	<div class="side-by-side">
		<div class="side">
			<p class="side-label">source</p>
			<pre class="side-text">{conflict.source?.text ?? '(removed)'}</pre>
		</div>
		<div class="side">
			<p class="side-label">target</p>
			<pre class="side-text">{conflict.target?.text ?? '(removed)'}</pre>
		</div>
	</div>
{/snippet}

<style>
	.merge-report {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
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
	.status {
		text-transform: uppercase;
		font-size: 0.66rem;
		letter-spacing: 0.14em;
	}
	.status-code_conflicted,
	.status-context_conflicted,
	.status-both_conflicted {
		color: var(--color-danger);
	}
	.status-ready {
		color: var(--color-primary);
	}
	.block {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
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
		gap: 0.4rem;
		font-size: 0.78rem;
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.conflict-file {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.45rem 0.55rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 0.5rem;
		background: color-mix(in srgb, var(--color-surface-elevated) 70%, transparent);
	}
	.conflict-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.6rem;
	}
	.preview {
		margin: 0;
		font-size: 0.7rem;
		max-height: 9rem;
		overflow: auto;
		padding: 0.4rem;
		background: var(--color-surface-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.4rem;
		white-space: pre-wrap;
	}
	.explanation {
		margin: 0;
		color: var(--color-text-muted);
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
		font-size: 0.62rem;
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
	.resolve-form {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.textarea {
		width: 100%;
		resize: vertical;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 0.6rem;
		background: rgb(11 12 10 / 0.92);
		padding: 0.5rem 0.65rem;
		font: inherit;
		font-size: 0.8rem;
		color: var(--color-text);
		min-height: 4.2rem;
	}
	.resolve-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}
	.hint {
		font-size: 0.62rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.btn {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 88%, black);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.35rem 0.75rem;
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
	}
	.btn--primary {
		border-color: color-mix(in srgb, var(--color-primary) 52%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 22%, rgb(18 19 15 / 1));
		color: var(--color-primary);
	}
	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
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
