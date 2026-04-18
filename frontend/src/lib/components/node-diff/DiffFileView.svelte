<script lang="ts">
	import type { FileDiff } from '$lib/features/node-diff/schemas';

	interface Props {
		file: FileDiff | null;
		summary: string | null;
		summaryLoading?: boolean;
		summaryError?: string | null;
		summaryCached?: boolean;
		onRequestSummary: () => void;
	}

	let {
		file,
		summary,
		summaryLoading = false,
		summaryError = null,
		summaryCached = false,
		onRequestSummary
	}: Props = $props();

	const lineClasses = {
		context: 'bg-transparent text-text-muted',
		add: 'bg-emerald-400/10 text-emerald-100',
		remove: 'bg-rose-400/10 text-rose-100'
	} as const;
</script>

{#if !file}
	<section
		class="rounded-2xl border border-dashed border-border bg-surface/40 p-5 text-xs text-text-muted sm:text-sm"
	>
		Select a changed file to inspect its diff.
	</section>
{:else}
	<section class="flex h-full min-h-0 flex-col gap-3">
		<header class="rounded-2xl border border-border bg-surface/80 p-3">
			<h3 class="truncate text-sm font-semibold text-text sm:text-base" title={file.path}>
				{file.path}
			</h3>
			<div class="mt-2 flex flex-wrap items-center justify-between gap-2.5">
				<p class="text-xs text-text-muted capitalize">
					{file.changeType} · {file.hunks.length} hunk{file.hunks.length === 1 ? '' : 's'}
				</p>

				<div class="flex flex-wrap items-center gap-1.5 text-xs font-medium">
					<span class="rounded-full bg-emerald-400/10 px-2 py-0.5 text-emerald-100"
						>+{file.additions}</span
					>
					<span class="rounded-full bg-rose-400/10 px-2 py-0.5 text-rose-100"
						>-{file.deletions}</span
					>
					<button
						type="button"
						class="rounded-full border border-border bg-surface-elevated px-2.5 py-1 text-[11px] text-text transition hover:bg-surface"
						onclick={onRequestSummary}
						disabled={summaryLoading}
					>
						{summary ? 'Refresh summary' : 'Load summary'}
					</button>
				</div>
			</div>
		</header>

		{#if summaryLoading || summaryError || summary}
			<section class="rounded-2xl border border-border bg-surface/80 p-3">
				<div class="flex items-center justify-between gap-2">
					<h4 class="text-[11px] font-semibold tracking-[0.18em] text-text uppercase">
						File summary
					</h4>
					<div class="flex items-center gap-1.5 text-[11px] text-text-muted">
						{#if summaryCached}
							<span class="rounded-full border border-border bg-surface-elevated px-1.5 py-0.5"
								>cached</span
							>
						{/if}
						{#if summaryLoading}
							<span>Generating…</span>
						{/if}
					</div>
				</div>

				{#if summaryError}
					<p class="mt-2 text-xs text-danger sm:text-sm">{summaryError}</p>
				{:else if summary}
					<p class="mt-2 text-xs leading-5 text-text-muted sm:text-sm sm:leading-6">{summary}</p>
				{/if}
			</section>
		{/if}

		<div class="min-h-0 flex-1 overflow-auto rounded-2xl border border-border bg-[#0d1117]">
			<div
				class="min-w-full divide-y divide-white/5 font-mono text-[11px] leading-5 text-slate-200 sm:text-xs sm:leading-5"
			>
				{#each file.hunks as hunk (hunk.header)}
					<section>
						<div class="sticky top-0 z-10 bg-sky-400/10 px-3 py-1.5 text-[11px] text-sky-100">
							{hunk.header}
						</div>
						{#each hunk.lines as line, index (`${hunk.header}-${index}`)}
							<div class={`grid grid-cols-[2rem_1fr] gap-2 px-3 py-0.5 ${lineClasses[line.type]}`}>
								<div class="text-right text-[9px] text-slate-500 select-none">{index + 1}</div>
								<pre class="overflow-x-auto break-words whitespace-pre-wrap">{line.type === 'add'
										? '+'
										: line.type === 'remove'
											? '-'
											: ' '}{line.content}</pre>
							</div>
						{/each}
					</section>
				{/each}
			</div>
		</div>
	</section>
{/if}
