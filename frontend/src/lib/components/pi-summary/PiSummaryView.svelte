<script lang="ts">
	import PiSummarySection from './PiSummarySection.svelte';
	import { parsePiSummary } from '$lib/features/pi-summary/parse';

	interface Props {
		summary: string;
		label?: string;
	}

	let { summary, label = 'Pi summary format' }: Props = $props();

	const document = $derived(parsePiSummary(summary));

	function shouldAutoExpand(title: string) {
		return /user intent|open questions|suggested next step/i.test(title);
	}
</script>

<section class="rounded-2xl border border-border bg-surface/70 p-4 md:p-5">
	<div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
		<div>
			<p class="text-sm font-medium tracking-[0.2em] text-primary-accent uppercase">{label}</p>
			<h2 class="mt-1.5 text-xl font-semibold text-text">{document.title}</h2>
			<p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
				Collapsible sections keep the node view compact while still exposing the structured summary
				that Pi returns.
			</p>
		</div>
	</div>

	<div class="mt-4 flex flex-col gap-2.5">
		{#each document.sections as section (section.id)}
			<PiSummarySection {section} open={shouldAutoExpand(section.title)} />
		{/each}
	</div>
</section>
