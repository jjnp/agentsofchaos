<script lang="ts">
	import type { AgentNode } from '$lib/agent-graph/types';

	let {
		selectedNode = null,
		isOpen = true,
		prompt = $bindable('')
	}: {
		selectedNode?: AgentNode | null;
		isOpen?: boolean;
		prompt?: string;
	} = $props();

	const terminalLines = [
		'[agent] attaching to active node stream…',
		'[agent] replaying latest execution output…',
		'',
		'> Parsing branch context and assembling task state',
		'> Reviewing parent lineage and merged notes',
		'> Preparing next message chunk for the selected node',
		'',
		'lorem ipsum dolor sit amet, consectetur adipiscing elit.',
		'consequat id porta vitae, pretium non velit, sed tempor risus.',
		'mauris placerat erat vel magna fermentum, non ultrices nibh feugiat.'
	];
</script>

{#if isOpen}
	<aside class="node-view-sidebar" aria-label="Node view">
		<header class="node-view-sidebar__header">
			{#if selectedNode}
				<h2 class="node-view-sidebar__title">{selectedNode.name}</h2>
				<p class="node-view-sidebar__status">Status: {selectedNode.status}</p>
			{:else}
				<h2 class="node-view-sidebar__title">No node selected</h2>
				<p class="node-view-sidebar__status">Select a node in the canvas to inspect it here.</p>
			{/if}
		</header>

		<div class="node-view-sidebar__terminal" role="log" aria-live="polite">
			{#each terminalLines as line, index (`${index}-${line}`)}
				<p>{line}</p>
			{/each}
		</div>

		<div class="node-view-sidebar__composer">
			<label class="node-view-sidebar__composer-label" for="node-view-prompt">Prompt</label>
			<textarea
				id="node-view-prompt"
				class="node-view-sidebar__textarea"
				bind:value={prompt}
				rows="4"
				placeholder="Write the next instruction for this node…"
			></textarea>
		</div>
	</aside>
{/if}

<style>
	.node-view-sidebar {
		position: absolute;
		top: 1rem;
		left: 1rem;
		bottom: 1rem;
		z-index: 20;
		width: min(42rem, 46vw);
		display: grid;
		grid-template-rows: auto minmax(0, 1fr) auto;
		gap: 1rem;
		padding: 1.1rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 1.6rem;
		background: rgb(18 19 15 / 0.9);
		backdrop-filter: blur(18px);
		box-shadow: var(--shadow-panel);
	}

	.node-view-sidebar__header {
		display: grid;
		gap: 0.25rem;
	}

	.node-view-sidebar__title {
		font-size: 1.05rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.node-view-sidebar__status {
		font-size: 0.76rem;
		color: color-mix(in srgb, var(--color-primary) 42%, var(--color-text));
		text-transform: capitalize;
	}

	.node-view-sidebar__terminal {
		overflow: auto;
		border-radius: 1.1rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: linear-gradient(180deg, rgb(10 10 9 / 0.98), rgb(14 15 12 / 0.94));
		padding: 1rem;
		font-family:
			'Berkeley Mono', 'JetBrains Mono', 'SFMono-Regular', Menlo, Monaco, Consolas, monospace;
		font-size: 0.78rem;
		line-height: 1.55;
		color: #cfd7bc;
		white-space: pre-wrap;
	}

	.node-view-sidebar__terminal p {
		margin: 0;
	}

	.node-view-sidebar__composer {
		display: grid;
		gap: 0.45rem;
	}

	.node-view-sidebar__composer-label {
		font-size: 0.68rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}

	.node-view-sidebar__textarea {
		width: 100%;
		resize: vertical;
		min-height: 6.5rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 84%, transparent);
		border-radius: 1rem;
		background: rgb(11 12 10 / 0.92);
		padding: 0.9rem 1rem;
		font: inherit;
		color: var(--color-text);
	}

	.node-view-sidebar__textarea:focus {
		outline: 1px solid color-mix(in srgb, var(--color-primary) 52%, transparent);
		outline-offset: 0;
	}

	.node-view-sidebar__textarea::placeholder {
		color: var(--color-text-muted);
	}

	@media (max-width: 900px) {
		.node-view-sidebar {
			width: min(32rem, calc(100vw - 5rem));
		}
	}

	@media (max-width: 640px) {
		.node-view-sidebar {
			top: 0.75rem;
			left: 0.75rem;
			right: 4.25rem;
			bottom: 0.75rem;
			width: auto;
		}
	}
</style>
