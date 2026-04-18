<script lang="ts">
	import Dropdown from '$lib/components/primitives/Dropdown.svelte';
	import type { ControlOption } from '$lib/components/primitives/types';
	import type { ExplainMode } from '$lib/orchestrator/contracts';
	import type { LayoutMode } from '$lib/agent-graph/types';

	type ConnectionStatus = 'connecting' | 'open' | 'error';

	let {
		activeLayoutMode = $bindable<LayoutMode>('rings'),
		showNodeDetailsForAll = $bindable(true),
		layoutModeOptions,
		isOpen = $bindable(true),
		connectionStatus = 'connecting' as ConnectionStatus,
		instanceCount = 0,
		explainMode = $bindable<ExplainMode>('direct'),
		onCreateRoot,
		onRefresh,
		onRecenter,
		isCreateDisabled = false,
		isRefreshDisabled = false,
		isRecenterDisabled = false
	}: {
		activeLayoutMode?: LayoutMode;
		showNodeDetailsForAll?: boolean;
		layoutModeOptions: readonly ControlOption[];
		isOpen?: boolean;
		connectionStatus?: ConnectionStatus;
		instanceCount?: number;
		explainMode?: ExplainMode;
		onCreateRoot?: () => void;
		onRefresh?: () => void;
		onRecenter?: () => void;
		isCreateDisabled?: boolean;
		isRefreshDisabled?: boolean;
		isRecenterDisabled?: boolean;
	} = $props();

	const handleLayoutModeSelect = (option: ControlOption) => {
		activeLayoutMode = option.value as LayoutMode;
	};
</script>

<div class="canvas-sidebar">
	{#if !isOpen}
		<button
			type="button"
			class="canvas-sidebar__toggle canvas-sidebar__toggle--floating"
			onclick={() => {
				isOpen = true;
			}}
			aria-expanded="false"
			aria-controls="agent-canvas-sidebar-panel"
		>
			Show controls
		</button>
	{/if}

	<aside
		id="agent-canvas-sidebar-panel"
		class:canvas-sidebar__panel--open={isOpen}
		class="canvas-sidebar__panel"
	>
		<div class="canvas-sidebar__panel-header">
			<div class="canvas-sidebar__spacer"></div>
			<button
				type="button"
				class="canvas-sidebar__toggle"
				onclick={() => {
					isOpen = false;
				}}
				aria-expanded="true"
				aria-controls="agent-canvas-sidebar-panel"
			>
				Hide controls
			</button>
		</div>

		<section class="canvas-sidebar__section">
			<div class="canvas-sidebar__stat-row">
				<div>
					<p class="canvas-sidebar__section-label">Connection</p>
					<p class={`canvas-sidebar__status canvas-sidebar__status--${connectionStatus}`}>
						{connectionStatus}
					</p>
				</div>
				<div>
					<p class="canvas-sidebar__section-label">Live nodes</p>
					<p class="canvas-sidebar__value">{instanceCount}</p>
				</div>
			</div>
			<div class="canvas-sidebar__actions-row">
				<button
					type="button"
					class="canvas-sidebar__action-button"
					onclick={() => onCreateRoot?.()}
					disabled={isCreateDisabled}
				>
					New root
				</button>
				<button
					type="button"
					class="canvas-sidebar__action-button canvas-sidebar__action-button--secondary"
					onclick={() => onRefresh?.()}
					disabled={isRefreshDisabled}
				>
					Refresh
				</button>
				<button
					type="button"
					class="canvas-sidebar__action-button canvas-sidebar__action-button--secondary"
					onclick={() => onRecenter?.()}
					disabled={isRecenterDisabled}
				>
					Recenter
				</button>
			</div>
		</section>

		<Dropdown
			label="Layout mode"
			options={layoutModeOptions}
			value={activeLayoutMode}
			onSelect={handleLayoutModeSelect}
		/>

		<section class="canvas-sidebar__section">
			<p class="canvas-sidebar__section-label">File explanations</p>
			<div class="canvas-sidebar__segmented-control" role="radiogroup" aria-label="File explanation mode">
				<button
					type="button"
					class:canvas-sidebar__segmented-control-button--active={explainMode === 'direct'}
					class="canvas-sidebar__segmented-control-button"
					onclick={() => {
						explainMode = 'direct';
					}}
				>
					Direct
				</button>
				<button
					type="button"
					class:canvas-sidebar__segmented-control-button--active={explainMode === 'ephemeral'}
					class="canvas-sidebar__segmented-control-button"
					onclick={() => {
						explainMode = 'ephemeral';
					}}
				>
					Ephemeral pi
				</button>
			</div>
		</section>

		<label class="canvas-sidebar__switch">
			<div>
				<span class="canvas-sidebar__switch-label">Node details</span>
				<p class="canvas-sidebar__switch-copy">Show the info cards for every node.</p>
			</div>
			<span class="canvas-sidebar__checkbox-wrap">
				<input
					type="checkbox"
					class="canvas-sidebar__checkbox"
					bind:checked={showNodeDetailsForAll}
					aria-label="Toggle node details"
				/>
			</span>
		</label>
	</aside>
</div>

<style>
	.canvas-sidebar {
		position: absolute;
		top: 1rem;
		right: 1rem;
		z-index: 20;
		pointer-events: none;
		display: grid;
		justify-items: end;
	}

	.canvas-sidebar__toggle,
	.canvas-sidebar__panel {
		pointer-events: auto;
	}

	.canvas-sidebar__toggle {
		border: 1px solid color-mix(in srgb, var(--color-border) 78%, transparent);
		background: rgb(18 19 15 / 0.92);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.7rem 1rem;
		font-size: 0.72rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		backdrop-filter: blur(18px);
		cursor: pointer;
		transition:
			transform 180ms ease,
			border-color 180ms ease,
			color 180ms ease;
	}

	.canvas-sidebar__toggle:hover {
		transform: translateX(-2px);
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
		color: var(--color-primary);
	}

	.canvas-sidebar__toggle--floating {
		position: absolute;
		top: 0;
		right: 0;
	}

	.canvas-sidebar__panel {
		width: min(22rem, calc(100vw - 4.5rem));
		display: grid;
		gap: 1rem;
		transform: translateX(calc(100% + 0.75rem));
		opacity: 0;
		border: 1px solid color-mix(in srgb, var(--color-border) 78%, transparent);
		background: rgb(18 19 15 / 0.9);
		border-radius: 1.5rem;
		padding: 1rem;
		backdrop-filter: blur(18px);
		transition:
			transform 220ms ease,
			opacity 220ms ease;
	}

	.canvas-sidebar__panel--open {
		transform: translateX(0);
		opacity: 1;
	}

	.canvas-sidebar__panel-header {
		display: flex;
		justify-content: flex-end;
	}

	.canvas-sidebar__spacer {
		flex: 1;
	}

	.canvas-sidebar__section {
		display: grid;
		gap: 0.75rem;
	}

	.canvas-sidebar__section-label {
		font-size: 0.68rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}

	.canvas-sidebar__stat-row {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}

	.canvas-sidebar__value,
	.canvas-sidebar__status {
		margin-top: 0.24rem;
		font-size: 0.84rem;
		font-weight: 600;
		color: var(--color-text);
		text-transform: capitalize;
	}

	.canvas-sidebar__status--open {
		color: var(--color-success);
	}

	.canvas-sidebar__status--connecting {
		color: var(--color-warning);
	}

	.canvas-sidebar__status--error {
		color: var(--color-danger);
	}

	.canvas-sidebar__actions-row {
		display: flex;
		gap: 0.6rem;
	}

	.canvas-sidebar__action-button,
	.canvas-sidebar__segmented-control-button {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 88%, black);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.65rem 0.9rem;
		font-size: 0.72rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		cursor: pointer;
		transition:
			transform 180ms ease,
			border-color 180ms ease,
			color 180ms ease,
			opacity 180ms ease;
	}

	.canvas-sidebar__action-button:hover:not(:disabled),
	.canvas-sidebar__segmented-control-button:hover:not(:disabled) {
		transform: translateY(-1px);
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
	}

	.canvas-sidebar__action-button:disabled,
	.canvas-sidebar__segmented-control-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.canvas-sidebar__action-button--secondary {
		background: transparent;
	}

	.canvas-sidebar__segmented-control {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.5rem;
	}

	.canvas-sidebar__segmented-control-button--active {
		border-color: color-mix(in srgb, var(--color-primary) 46%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 18%, rgb(18 19 15 / 1));
		color: var(--color-primary);
	}

	.canvas-sidebar__switch {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.2rem 0;
	}

	.canvas-sidebar__switch-label {
		display: block;
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.canvas-sidebar__switch-copy {
		margin-top: 0.2rem;
		font-size: 0.72rem;
		line-height: 1.4;
		color: var(--color-text-muted);
	}

	.canvas-sidebar__checkbox-wrap {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		flex-shrink: 0;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 0.7rem;
		background: color-mix(in srgb, var(--color-surface-elevated) 88%, black);
		box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.03);
	}

	.canvas-sidebar__checkbox {
		flex-shrink: 0;
		width: 1rem;
		height: 1rem;
		margin: 0;
		accent-color: var(--color-primary);
		cursor: pointer;
	}

	.canvas-sidebar__checkbox:hover,
	.canvas-sidebar__checkbox:focus-visible {
		outline: none;
		filter: brightness(1.08);
	}

	@media (max-width: 640px) {
		.canvas-sidebar {
			top: 0.75rem;
			right: 0.75rem;
			left: 0.75rem;
			bottom: auto;
			justify-content: flex-end;
		}

		.canvas-sidebar__panel {
			width: min(20rem, calc(100vw - 1.5rem));
		}
	}
</style>
