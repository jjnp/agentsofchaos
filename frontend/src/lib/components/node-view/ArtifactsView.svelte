<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { Artifact, ContextSnapshot, Node } from '$lib/orchestrator/contracts';

	interface Props {
		store: GraphStore;
		node: Node;
	}

	let { store, node }: Props = $props();

	let loading = $state(false);
	let error = $state<string | null>(null);
	let inlinePreviews = $state<Map<string, string>>(new Map());
	let previewLoading = $state<Set<string>>(new Set());

	const artifacts = $derived<readonly Artifact[]>(
		store.artifactsByNodeId.get(node.id) ?? []
	);
	// Pull the context snapshot too so we can list the files the agent
	// actually wrote/read at this node — those live on the snapshot
	// (`touched_files`, `read_files`), not on Artifact records. With
	// this section, the Artifacts tab covers the full data export
	// surface: reports + transcripts (durable artifacts) AND the raw
	// files the agent touched.
	const contextSnapshot = $derived<ContextSnapshot | null>(
		store.contextSnapshotsById.get(node.context_snapshot_id) ?? null
	);
	const touchedFiles = $derived<readonly string[]>(
		(contextSnapshot?.touched_files ?? []).map((ref) => ref.path).filter(Boolean)
	);
	const readOnlyFiles = $derived<readonly string[]>(
		(contextSnapshot?.read_files ?? [])
			.map((ref) => ref.path)
			.filter((path) => path && !touchedFiles.includes(path))
	);

	$effect(() => {
		const target = node.id;
		if (loading || store.artifactsByNodeId.has(target)) return;
		loading = true;
		error = null;
		void store
			.fetchArtifactsForNode(target)
			.catch((err: unknown) => {
				error = err instanceof Error ? err.message : String(err);
			})
			.finally(() => {
				loading = false;
			});
	});

	$effect(() => {
		const id = node.context_snapshot_id;
		if (store.contextSnapshotsById.has(id)) return;
		void store.fetchContextSnapshot(id).catch(() => {
			// Silent — surfaced via store.lastError elsewhere.
		});
	});

	function isInlineable(artifact: Artifact): boolean {
		return (
			artifact.media_type === 'application/json' ||
			artifact.kind === 'merge_report' ||
			artifact.kind === 'resolution_report' ||
			artifact.kind === 'context_projection_report'
		);
	}

	function formatBytes(n: number): string {
		if (n < 1024) return `${n} B`;
		if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
		return `${(n / 1024 / 1024).toFixed(1)} MB`;
	}

	function formatTime(value: string): string {
		const isoZ = /[Zz]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`;
		return new Date(isoZ).toLocaleString();
	}

	async function togglePreview(artifact: Artifact) {
		if (inlinePreviews.has(artifact.id)) {
			const next = new Map(inlinePreviews);
			next.delete(artifact.id);
			inlinePreviews = next;
			return;
		}
		const inflight = new Set(previewLoading);
		inflight.add(artifact.id);
		previewLoading = inflight;
		try {
			const response = await fetch(store.artifactContentUrl(artifact.id));
			if (!response.ok) {
				throw new Error(`HTTP ${response.status} fetching artifact content`);
			}
			let text = await response.text();
			// Pretty-print JSON if we can; fall back to raw text.
			try {
				text = JSON.stringify(JSON.parse(text), null, 2);
			} catch {
				/* not JSON; leave it */
			}
			const next = new Map(inlinePreviews);
			next.set(artifact.id, text);
			inlinePreviews = next;
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			const remaining = new Set(previewLoading);
			remaining.delete(artifact.id);
			previewLoading = remaining;
		}
	}
</script>

<section class="artifacts">
	<div class="bundle">
		<a
			class="bundle-link"
			href={store.nodeArchiveUrl(node.id)}
			download
			rel="noopener"
			target="_blank"
		>
			Download node tarball
		</a>
		<span class="dim small">All files at this node's snapshot, packaged as `git archive`.</span>
	</div>

	{#if touchedFiles.length > 0 || readOnlyFiles.length > 0}
		<section class="files">
			{#if touchedFiles.length > 0}
				<p class="section-label">Files written at this node</p>
				<ul class="list">
					{#each touchedFiles as path (path)}
						<li class="row file-row">
							<div class="head">
								<span class="kind">file</span>
								<p class="path mono">{path}</p>
							</div>
							<div class="actions">
								<a
									class="link"
									href={store.nodeFileContentUrl(node.id, path)}
									download={path.split('/').pop()}
									rel="noopener"
									target="_blank">Download</a
								>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
			{#if readOnlyFiles.length > 0}
				<p class="section-label muted">Files read but not modified</p>
				<ul class="list">
					{#each readOnlyFiles as path (path)}
						<li class="row file-row">
							<div class="head">
								<span class="kind dim">read</span>
								<p class="path mono">{path}</p>
							</div>
							<div class="actions">
								<a
									class="link"
									href={store.nodeFileContentUrl(node.id, path)}
									download={path.split('/').pop()}
									rel="noopener"
									target="_blank">Download</a
								>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}

	<p class="section-label">Reports &amp; transcripts</p>
	{#if loading && artifacts.length === 0}
		<p class="muted small">Loading artifacts…</p>
	{:else if error}
		<p class="error small">{error}</p>
	{:else if artifacts.length === 0}
		<p class="muted small">No artifacts recorded for this node.</p>
	{:else}
		<ul class="list">
			{#each artifacts as artifact (artifact.id)}
				<li class="row">
					<div class="head">
						<span class="kind">{artifact.kind}</span>
						<span class="dim small">{formatBytes(artifact.size_bytes)}</span>
						<span class="dim small">{formatTime(artifact.created_at)}</span>
					</div>
					<p class="path mono">{artifact.path}</p>
					<div class="actions">
						{#if isInlineable(artifact)}
							<button
								type="button"
								class="link"
								onclick={() => togglePreview(artifact)}
								disabled={previewLoading.has(artifact.id)}
							>
								{#if previewLoading.has(artifact.id)}
									Loading…
								{:else if inlinePreviews.has(artifact.id)}
									Hide preview
								{:else}
									Preview
								{/if}
							</button>
						{/if}
						<a
							class="link"
							href={store.artifactContentUrl(artifact.id)}
							download
							rel="noopener"
							target="_blank">Download</a
						>
					</div>
					{#if inlinePreviews.has(artifact.id)}
						<pre class="preview">{inlinePreviews.get(artifact.id)}</pre>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	.artifacts {
		display: grid;
		gap: 0.45rem;
		min-height: 0;
		overflow: auto;
		padding-right: 0.25rem;
	}
	.list {
		display: grid;
		gap: 0.45rem;
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.row {
		display: grid;
		gap: 0.3rem;
		padding: 0.45rem 0.55rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 0.6rem;
		background: rgb(12 13 10 / 0.6);
	}
	.head {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
		flex-wrap: wrap;
	}
	.kind {
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--color-primary);
	}
	.path {
		margin: 0;
		font-size: 0.7rem;
		color: var(--color-text);
		word-break: break-all;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
	}
	.link {
		background: none;
		border: none;
		padding: 0;
		font-size: 0.74rem;
		color: var(--color-primary-accent);
		cursor: pointer;
		text-decoration: none;
	}
	.link:hover {
		text-decoration: underline;
	}
	.link:disabled {
		opacity: 0.5;
		cursor: progress;
	}
	.preview {
		margin: 0;
		font-size: 0.7rem;
		max-height: 18rem;
		overflow: auto;
		padding: 0.5rem;
		background: var(--color-surface-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		white-space: pre-wrap;
	}
	.dim {
		color: var(--color-text-muted);
	}
	.section-label {
		font-size: 0.62rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
		margin: 0;
	}
	.files {
		display: grid;
		gap: 0.4rem;
	}
	.bundle {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.55rem;
		padding: 0.5rem 0.6rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 0.7rem;
		background: rgb(12 13 10 / 0.55);
	}
	.bundle-link {
		display: inline-block;
		padding: 0.35rem 0.7rem;
		border-radius: 999px;
		border: 1px solid color-mix(in srgb, var(--color-primary) 38%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 14%, transparent);
		color: var(--color-primary);
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		text-decoration: none;
	}
	.bundle-link:hover {
		border-color: color-mix(in srgb, var(--color-primary) 62%, var(--color-border));
	}
	.file-row .head {
		gap: 0.4rem;
	}
	.muted {
		color: var(--color-text-muted);
	}
	.small {
		font-size: 0.74rem;
	}
	.error {
		color: var(--color-danger);
	}
	.mono {
		font-family: var(--font-mono);
	}
</style>
