<script lang="ts">
	import TerminalStream from '$lib/components/TerminalStream.svelte';
	import type { MaterializedOrchestratorGraphNode } from '$lib/orchestrator/graph';

	let {
		selectedNode = null,
		isOpen = true,
		prompt = $bindable(''),
		onSubmit,
		onCreateInstance
	}: {
		selectedNode?: MaterializedOrchestratorGraphNode | null;
		isOpen?: boolean;
		prompt?: string;
		onSubmit?: () => void;
		onCreateInstance?: () => void;
	} = $props();

	const isSubmitDisabled = $derived(!selectedNode || prompt.trim().length === 0);
	const terminalOutput = $derived(selectedNode?.record.terminalOutput ?? '');
	const terminalStatus = $derived(selectedNode?.terminalMode ?? 'idle');

	const handleSubmit = () => {
		if (isSubmitDisabled) {
			return;
		}

		onSubmit?.();
	};
</script>

{#if isOpen}
	<aside class="node-view-sidebar" aria-label="Node view">
		<header class="node-view-sidebar__header">
			{#if selectedNode}
				<div class="node-view-sidebar__header-copy">
					<h2 class="node-view-sidebar__title">{selectedNode.node.name}</h2>
					<p class="node-view-sidebar__status">
						Slot {selectedNode.record.backend.slot + 1} · {selectedNode.record.backend.label} ·
						<span>{selectedNode.node.status}</span>
					</p>
				</div>
			{:else}
				<div class="node-view-sidebar__header-copy">
					<h2 class="node-view-sidebar__title">No node selected</h2>
					<p class="node-view-sidebar__status">
						Create or select an instance in the graph to inspect its output and continue work.
					</p>
				</div>
			{/if}
		</header>

		<div class="node-view-sidebar__body">
			<section class="node-view-sidebar__terminal-shell">
				<TerminalStream
					title={selectedNode ? `${selectedNode.record.backend.label} output` : 'Node output'}
					feedText={terminalOutput}
					feedStatus={terminalStatus}
					readOnly={true}
				/>
			</section>
		</div>

		<div class="node-view-sidebar__composer">
			<label class="node-view-sidebar__composer-label" for="node-view-prompt">Prompt</label>
			<textarea
				id="node-view-prompt"
				class="node-view-sidebar__textarea"
				bind:value={prompt}
				rows="4"
				placeholder="Write the next instruction for this node…"
				disabled={!selectedNode}
				onkeydown={(event) => {
					if (event.key === 'Enter' && !event.shiftKey) {
						event.preventDefault();
						handleSubmit();
					}
				}}
			></textarea>
			<div class="node-view-sidebar__composer-actions">
				{#if !selectedNode}
					<button
						type="button"
						class="node-view-sidebar__secondary"
						onclick={() => {
							onCreateInstance?.();
						}}
					>
						Create instance
					</button>
				{:else}
					<button
						type="button"
						class="node-view-sidebar__submit"
						disabled={isSubmitDisabled}
						onclick={handleSubmit}
					>
						Send
					</button>
				{/if}
			</div>
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

	.node-view-sidebar__header-copy {
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
		text-transform: none;
	}

	.node-view-sidebar__status span {
		text-transform: capitalize;
	}

	.node-view-sidebar__body {
		overflow: auto;
		display: grid;
		gap: 1rem;
		align-content: start;
		padding-right: 0.15rem;
	}

	.node-view-sidebar__terminal-shell {
		min-height: 28rem;
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

	.node-view-sidebar__textarea:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.node-view-sidebar__textarea::placeholder {
		color: var(--color-text-muted);
	}

	.node-view-sidebar__composer-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.65rem;
	}

	.node-view-sidebar__submit,
	.node-view-sidebar__secondary {
		border-radius: 999px;
		padding: 0.65rem 1rem;
		font-size: 0.74rem;
		font-weight: 600;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
		transition:
			transform 180ms ease,
			filter 180ms ease,
			opacity 180ms ease;
	}

	.node-view-sidebar__submit {
		border: 1px solid color-mix(in srgb, var(--color-primary) 48%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 24%, rgb(18 19 15 / 1));
		color: var(--color-text);
	}

	.node-view-sidebar__secondary {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 90%, black);
		color: var(--color-text);
	}

	.node-view-sidebar__submit:hover:not(:disabled),
	.node-view-sidebar__secondary:hover:not(:disabled) {
		transform: translateY(-1px);
		filter: brightness(1.06);
	}

	.node-view-sidebar__submit:disabled,
	.node-view-sidebar__secondary:disabled {
		opacity: 0.45;
		cursor: not-allowed;
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
