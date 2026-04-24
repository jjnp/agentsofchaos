<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';

	interface Props {
		store: GraphStore;
		onCloseProject: () => void;
	}

	let { store, onCloseProject }: Props = $props();

	let isOpen = $state(true);
	let creatingRoot = $state(false);
	let rootError = $state<string | null>(null);

	const hasRoot = $derived(store.rootNodes.length > 0);
	const connectionLabel = $derived.by(() => {
		switch (store.connectionStatus) {
			case 'connecting':
				return 'connecting';
			case 'open':
				return 'live';
			case 'closed':
				return 'disconnected';
			case 'error':
				return 'error';
			default:
				return 'idle';
		}
	});

	async function handleCreateRoot() {
		creatingRoot = true;
		rootError = null;
		try {
			await store.createRootNode();
		} catch (err) {
			rootError = err instanceof Error ? err.message : String(err);
		} finally {
			creatingRoot = false;
		}
	}
</script>

<div class="canvas-controls">
	{#if !isOpen}
		<button
			type="button"
			class="toggle floating"
			onclick={() => {
				isOpen = true;
			}}
			aria-expanded="false"
			aria-controls="canvas-controls-panel"
		>
			Show controls
		</button>
	{/if}

	<aside
		id="canvas-controls-panel"
		class="panel"
		class:panel--open={isOpen}
		aria-label="Canvas controls"
	>
		<div class="panel-header">
			<span class="eyebrow">Side controls</span>
			<button
				type="button"
				class="toggle"
				onclick={() => {
					isOpen = false;
				}}
				aria-expanded="true"
				aria-controls="canvas-controls-panel"
			>
				Hide
			</button>
		</div>

		<section class="section">
			<div class="stat-row">
				<div>
					<p class="label">Connection</p>
					<p class="status" data-status={store.connectionStatus}>{connectionLabel}</p>
				</div>
				<div>
					<p class="label">Live nodes</p>
					<p class="value">{store.nodes.length}</p>
				</div>
			</div>
			<div class="actions-row">
				{#if !hasRoot}
					<button
						type="button"
						class="action primary"
						onclick={handleCreateRoot}
						disabled={creatingRoot}
					>
						{creatingRoot ? 'Creating…' : 'New root'}
					</button>
				{/if}
				<button
					type="button"
					class="action secondary"
					onclick={() => void store.refreshGraph()}
				>
					Refresh
				</button>
			</div>
			{#if rootError}
				<p class="error">{rootError}</p>
			{/if}
		</section>

		<section class="section">
			<p class="label">Project</p>
			<p class="path mono">{store.project?.root_path ?? ''}</p>
			<button type="button" class="action secondary" onclick={onCloseProject}>
				Close project
			</button>
		</section>

		<section class="section">
			<p class="label">Layout mode</p>
			<div class="segmented" role="radiogroup" aria-label="Layout mode">
				<button
					type="button"
					class="seg"
					class:seg--active={store.activeLayoutMode === 'rings'}
					aria-pressed={store.activeLayoutMode === 'rings'}
					onclick={() => store.setLayoutMode('rings')}
				>
					Rings
				</button>
				<button
					type="button"
					class="seg"
					class:seg--active={store.activeLayoutMode === 'tree'}
					aria-pressed={store.activeLayoutMode === 'tree'}
					onclick={() => store.setLayoutMode('tree')}
				>
					Tree
				</button>
				<button
					type="button"
					class="seg"
					class:seg--active={store.activeLayoutMode === 'force'}
					aria-pressed={store.activeLayoutMode === 'force'}
					onclick={() => store.setLayoutMode('force')}
				>
					Force
				</button>
			</div>
			<button type="button" class="action secondary" onclick={() => store.requestRecenter()}>
				Recenter
			</button>
		</section>
	</aside>
</div>

<style>
	.canvas-controls {
		position: absolute;
		top: 1rem;
		right: 1rem;
		z-index: 20;
		pointer-events: none;
		display: grid;
		justify-items: end;
	}
	.toggle,
	.panel {
		pointer-events: auto;
	}
	.toggle {
		border: 1px solid color-mix(in srgb, var(--color-border) 78%, transparent);
		background: rgb(18 19 15 / 0.92);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.55rem 0.9rem;
		font-size: 0.7rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		backdrop-filter: blur(18px);
		cursor: pointer;
		transition:
			transform 180ms ease,
			border-color 180ms ease,
			color 180ms ease;
	}
	.toggle:hover {
		transform: translateX(-2px);
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
		color: var(--color-primary);
	}
	.toggle.floating {
		position: absolute;
		top: 0;
		right: 0;
	}
	.panel {
		width: min(22rem, calc(100vw - 4.5rem));
		display: grid;
		gap: 1rem;
		transform: translateX(calc(100% + 0.75rem));
		opacity: 0;
		border: 1px solid color-mix(in srgb, var(--color-border) 78%, transparent);
		background: rgb(18 19 15 / 0.9);
		border-radius: 1.5rem;
		padding: 1rem 1.1rem;
		backdrop-filter: blur(18px);
		box-shadow: var(--shadow-panel);
		transition:
			transform 220ms ease,
			opacity 220ms ease;
	}
	.panel--open {
		transform: translateX(0);
		opacity: 1;
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	.eyebrow,
	.label {
		font-size: 0.68rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.section {
		display: grid;
		gap: 0.6rem;
	}
	.stat-row {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}
	.value,
	.status {
		margin-top: 0.24rem;
		font-size: 0.84rem;
		font-weight: 600;
		color: var(--color-text);
		text-transform: capitalize;
	}
	.status[data-status='open'] {
		color: var(--color-success);
	}
	.status[data-status='connecting'] {
		color: var(--color-warning);
	}
	.status[data-status='error'] {
		color: var(--color-danger);
	}
	.path {
		font-size: 0.78rem;
		color: var(--color-text);
		word-break: break-all;
	}
	.actions-row {
		display: flex;
		gap: 0.5rem;
	}
	.action,
	.seg {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 88%, black);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.6rem 0.9rem;
		font-size: 0.7rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
		transition:
			transform 180ms ease,
			border-color 180ms ease,
			color 180ms ease,
			opacity 180ms ease;
	}
	.action:hover:not(:disabled),
	.seg:hover:not(:disabled) {
		transform: translateY(-1px);
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
	}
	.action:disabled,
	.seg:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.action.secondary {
		background: transparent;
	}
	.action.primary {
		border-color: color-mix(in srgb, var(--color-primary) 52%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 22%, rgb(18 19 15 / 1));
		color: var(--color-primary);
	}
	.segmented {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.4rem;
	}
	.seg--active {
		border-color: color-mix(in srgb, var(--color-primary) 46%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 18%, rgb(18 19 15 / 1));
		color: var(--color-primary);
	}
	.error {
		color: var(--color-danger);
		font-size: 0.75rem;
	}
	.mono {
		font-family: var(--font-mono);
	}
</style>
