<script lang="ts">
	import type { PiSummarySection } from '$lib/features/pi-summary/parse';

	interface Props {
		section: PiSummarySection;
		open?: boolean;
	}

	let { section, open = false }: Props = $props();

	const progressSteps = $derived(
		section.blocks.flatMap((block) => (block.type === 'progress-steps' ? (block.steps ?? []) : []))
	);
	const completedProgressSteps = $derived(
		progressSteps.filter((step) => step.status === 'done').length
	);

	const stepIcon = {
		done: '✓',
		pending: '○',
		note: '•'
	} as const;

	const stepIconClasses = {
		done: 'text-emerald-300',
		pending: 'text-amber-300',
		note: 'text-sky-300'
	} as const;
</script>

<details class="rounded-xl border border-border bg-surface/75" {open}>
	<summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
		<div>
			<h3 class="text-sm font-semibold tracking-[0.18em] text-text uppercase">{section.title}</h3>
		</div>
		<div class="flex items-center gap-2">
			{#if progressSteps.length > 0}
				<span
					class="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-xs text-emerald-100"
				>
					{completedProgressSteps}/{progressSteps.length} steps
				</span>
			{/if}
			<span
				class="rounded-full border border-border bg-surface-elevated px-2 py-1 text-xs text-text-muted"
			>
				expand
			</span>
		</div>
	</summary>

	<div class="border-t border-border px-4 py-3">
		<div class="flex flex-col gap-3">
			{#each section.blocks as block, blockIndex (`${section.id}-${blockIndex}`)}
				{#if block.type === 'progress-steps' && block.steps}
					<ul class="space-y-1.5 text-sm leading-6 text-text-muted">
						{#each block.steps as step, stepIndex (`${section.id}-${stepIndex}-${step.label}`)}
							<li class="flex items-start gap-2.5">
								<span class={`mt-0.5 shrink-0 text-sm ${stepIconClasses[step.status]}`}>
									{stepIcon[step.status]}
								</span>
								<span>{step.label}</span>
							</li>
						{/each}
					</ul>
				{:else if block.type === 'bullet-list'}
					<ul class="space-y-1.5 pl-5 text-sm leading-6 text-text-muted">
						{#each block.content as item, itemIndex (`${section.id}-${itemIndex}-${item}`)}
							<li class="list-disc">{item}</li>
						{/each}
					</ul>
				{:else}
					{#each block.content as paragraph, paragraphIndex (`${section.id}-${paragraphIndex}-${paragraph}`)}
						<p class="text-sm leading-6 text-text-muted">{paragraph}</p>
					{/each}
				{/if}
			{/each}
		</div>
	</div>
</details>
