<script lang="ts">
	import PiSummarySection from './PiSummarySection.svelte';
	import { parsePiSummary } from '$lib/features/pi-summary/parse';

	interface Props {
		summary: string;
		label?: string;
	}

	let { summary, label = 'Pi summary format' }: Props = $props();

	const document = $derived(parsePiSummary(summary));
	// Empty state: the parser found a title but no `##`-delimited
	// sections. Most commonly: noop runs and very short pi runs whose
	// summary is a single paragraph. Render the raw summary as that
	// paragraph instead of the hackathon-era meta-explainer copy that
	// used to sit here unconditionally — the explainer made the card
	// look like a placeholder when the run actually had real content
	// in `summary` itself.
	const hasSections = $derived(document.sections.length > 0);
	const fallbackBody = $derived(summary.replace(/^#[^\n]*\n+/, '').trim());

	function shouldAutoExpand(title: string) {
		return /user intent|open questions|suggested next step/i.test(title);
	}
</script>

<section class="rounded-2xl border border-border bg-surface/70 p-3.5 md:p-4">
	<div class="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
		<div>
			<p class="text-[10px] font-medium tracking-[0.22em] text-primary-accent uppercase">{label}</p>
			<h2 class="mt-1 text-base font-semibold text-text sm:text-lg">{document.title}</h2>
		</div>
	</div>

	{#if hasSections}
		<div class="mt-3 flex flex-col gap-2">
			{#each document.sections as section (section.id)}
				<PiSummarySection {section} open={shouldAutoExpand(section.title)} />
			{/each}
		</div>
	{:else if fallbackBody}
		<p class="mt-2 text-xs leading-5 whitespace-pre-wrap text-text-muted sm:text-sm sm:leading-6">
			{fallbackBody}
		</p>
	{/if}
</section>
