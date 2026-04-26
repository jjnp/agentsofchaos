<script lang="ts">
	import type { FileDiff } from '$lib/orchestrator/contracts';

	interface Props {
		file: FileDiff | null;
		// URL to download the raw file at the parent node's snapshot.
		// Provided by `NodeDiffViewer` once the node id + path are known;
		// falls through as `null` for `deleted` files (nothing to fetch
		// at the new snapshot — the file is gone).
		downloadUrl?: string | null;
	}

	let { file, downloadUrl = null }: Props = $props();
</script>

{#if !file}
	<section class="empty">Select a changed file to inspect its diff.</section>
{:else}
	<section class="file">
		<header>
			<h3 title={file.path}>{file.path}</h3>
			<div class="meta">
				<span class="kind">{file.change_type}</span>
				<span class="hunks">
					{file.hunks.length} hunk{file.hunks.length === 1 ? '' : 's'}
				</span>
				<span class="add">+{file.additions}</span>
				<span class="del">-{file.deletions}</span>
				{#if downloadUrl}
					<a class="download" href={downloadUrl} download={file.path.split('/').pop()}>
						Download
					</a>
				{/if}
			</div>
		</header>

		<div class="hunks-wrap">
			{#each file.hunks as hunk (hunk.header)}
				<section class="hunk">
					<div class="hunk-header">{hunk.header}</div>
					{#each hunk.lines as line, index (`${hunk.header}-${index}`)}
						<div class="line line--{line.type}">
							<span class="ln" aria-hidden="true">{index + 1}</span>
							<pre>{line.type === 'add'
									? '+'
									: line.type === 'remove'
										? '-'
										: ' '}{line.content}</pre>
						</div>
					{/each}
				</section>
			{/each}
		</div>
	</section>
{/if}

<style>
	.empty {
		padding: 1rem;
		font-size: 0.78rem;
		color: var(--color-text-muted);
		border: 1px dashed color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 1rem;
		background: rgb(11 12 10 / 0.45);
	}
	.file {
		display: flex;
		flex-direction: column;
		min-height: 0;
		gap: 0.55rem;
	}
	header {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		padding: 0.65rem 0.85rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 1rem;
		background: rgb(12 13 10 / 0.78);
	}
	header h3 {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		font-size: 0.7rem;
		font-family: var(--font-mono);
	}
	.kind,
	.hunks {
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.add {
		color: var(--color-success);
	}
	.del {
		color: var(--color-danger);
	}
	.download {
		margin-left: auto;
		padding: 0.18rem 0.55rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 80%, black);
		color: var(--color-text);
		border-radius: 999px;
		font-family: var(--font-mono);
		font-size: 0.66rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		text-decoration: none;
	}
	.download:hover {
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
		color: var(--color-primary);
	}

	.hunks-wrap {
		min-height: 0;
		overflow: auto;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 1rem;
		background: #0d1117;
	}
	.hunk + .hunk {
		border-top: 1px solid rgb(255 255 255 / 0.06);
	}
	.hunk-header {
		position: sticky;
		top: 0;
		z-index: 1;
		padding: 0.35rem 0.85rem;
		background: rgb(56 139 253 / 0.14);
		color: rgb(190 220 255 / 0.94);
		font-family: var(--font-mono);
		font-size: 0.7rem;
	}
	.line {
		display: grid;
		grid-template-columns: 2rem 1fr;
		gap: 0.5rem;
		padding: 0 0.85rem;
		font-family: var(--font-mono);
		font-size: 0.72rem;
		line-height: 1.5;
	}
	.line--context {
		color: var(--color-text-muted);
	}
	.line--add {
		background: color-mix(in srgb, var(--color-success) 8%, transparent);
		color: #b8efb8;
	}
	.line--remove {
		background: color-mix(in srgb, var(--color-danger) 10%, transparent);
		color: #ffb6b3;
	}
	.ln {
		text-align: right;
		font-size: 0.6rem;
		color: rgb(120 130 140 / 0.7);
		user-select: none;
	}
	pre {
		white-space: pre-wrap;
		word-break: break-word;
		margin: 0;
	}
</style>
