<script lang="ts">
	const roadmapItems = [
		'Fast-moving tactical dashboard surfaces',
		'Reusable UI primitives backed by strict TypeScript models',
		'Tailwind-first styling with room for focused custom CSS where needed'
	] as const;
</script>

<svelte:head>
	<title>Agents of Chaos</title>
	<meta
		name="description"
		content="Early visual direction for the Agents of Chaos frontend application."
	/>
</svelte:head>

<div class="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-16 md:px-10">
	<div class="grid w-full gap-8 lg:grid-cols-[1.2fr_0.8fr]">
		<section class="panel flex flex-col gap-8 p-8 md:p-12">
			<div class="flex flex-col gap-4">
				<span class="badge w-fit">Frontend foundation</span>
				<h1 class="max-w-3xl text-4xl font-semibold tracking-tight text-balance md:text-6xl">
					Agents of Chaos is ready for a bespoke interface.
				</h1>
				<p class="section-copy">
					The Svelte starter content has been stripped back so the project can grow around the
					actual product direction. Tailwind CSS is the default styling layer, with semantic theme
					variables defined directly in the design system stylesheet for reusable components.
				</p>
			</div>

			<div class="grid gap-4 md:grid-cols-3">
				{#each roadmapItems as item (item)}
					<div
						class="rounded-2xl border border-border/80 bg-surface-elevated/80 p-4 text-sm leading-6 text-text-muted"
					>
						{item}
					</div>
				{/each}
			</div>
		</section>

		<aside class="panel flex flex-col gap-6 p-8">
			<div>
				<p class="text-sm font-medium tracking-[0.2em] text-primary-accent uppercase">Theme</p>
				<h2 class="mt-3 text-2xl font-semibold text-text">Semantic Tailwind theme variables</h2>
			</div>

			<div class="grid gap-3">
				<div
					class="flex items-center justify-between rounded-2xl border border-border bg-canvas/70 px-4 py-3"
				>
					<span class="text-sm text-text-muted">Canvas</span>
					<span class="h-4 w-16 rounded-full bg-canvas"></span>
				</div>
				<div
					class="flex items-center justify-between rounded-2xl border border-border bg-surface-elevated/70 px-4 py-3"
				>
					<span class="text-sm text-text-muted">Surface</span>
					<span class="h-4 w-16 rounded-full bg-surface"></span>
				</div>
				<div
					class="flex items-center justify-between rounded-2xl border border-border bg-surface-elevated/70 px-4 py-3"
				>
					<span class="text-sm text-text-muted">Primary</span>
					<span class="h-4 w-16 rounded-full bg-primary"></span>
				</div>
				<div
					class="flex items-center justify-between rounded-2xl border border-border bg-surface-elevated/70 px-4 py-3"
				>
					<span class="text-sm text-text-muted">Accent</span>
					<span class="h-4 w-16 rounded-full bg-primary-accent"></span>
				</div>
			</div>

			<p class="text-sm leading-7 text-text-muted">
				An uncommitted <code class="rounded bg-canvas px-2 py-1 text-text">example/</code> folder can
				inform future UI work without becoming part of the codebase.
			</p>
		</aside>
	</div>
</div>
