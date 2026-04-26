<script lang="ts">
	interface Props {
		title: string;
		body: string;
		loading?: boolean;
		error?: string | null;
		sourceLabel?: string | null;
		cached?: boolean;
	}

	let {
		title,
		body,
		loading = false,
		error = null,
		sourceLabel = null,
		cached = false
	}: Props = $props();
</script>

<section class="rounded-2xl border border-border bg-surface/80 p-4">
	<div class="flex items-center justify-between gap-3">
		<h3 class="text-sm font-semibold tracking-[0.18em] text-text uppercase">{title}</h3>
		<div class="flex items-center gap-2 text-xs text-text-muted">
			{#if sourceLabel}
				<span class="rounded-full border border-border bg-surface-elevated px-2 py-1"
					>{sourceLabel}</span
				>
			{/if}
			{#if cached}
				<span class="rounded-full border border-border bg-surface-elevated px-2 py-1">cached</span>
			{/if}
			{#if loading}
				<span>Generating…</span>
			{/if}
		</div>
	</div>

	{#if error}
		<p class="mt-3 text-sm leading-6 text-danger">{error}</p>
	{:else}
		<p class="mt-3 text-sm leading-6 text-text-muted">{body}</p>
	{/if}
</section>
