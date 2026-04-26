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

<section class="rounded-2xl border border-border bg-surface/70 p-3.5 md:p-4">
	<div class="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
		<div>
			<p class="text-[10px] font-medium tracking-[0.22em] text-primary-accent uppercase">{label}</p>
			<h2 class="mt-1 text-base font-semibold text-text sm:text-lg">{document.title}</h2>
			<p class="mt-1.5 max-w-3xl text-xs leading-5 text-text-muted sm:text-sm">
				Collapsible sections keep the node view compact while still exposing the structured summary
				that Pi returns.
			</p>
		</div>
	</div>

	<div class="mt-3 flex flex-col gap-2">
		{#each document.sections as section (section.id)}
			<PiSummarySection {section} open={shouldAutoExpand(section.title)} />
		{/each}
	</div>
</section>
