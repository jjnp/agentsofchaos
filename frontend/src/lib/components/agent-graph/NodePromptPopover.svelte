<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { Node, Run } from '$lib/orchestrator/contracts';

	import TerminalOutput from '../node-view/TerminalOutput.svelte';

	interface Props {
		store: GraphStore;
		node: Node;
		screenX: number;
		screenY: number;
	}

	let { store, node, screenX, screenY }: Props = $props();

	let prompt = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let textareaEl = $state<HTMLTextAreaElement | null>(null);

	const originatingRun = $derived<Run | null>(
		node.originating_run_id ? (store.runsById.get(node.originating_run_id) ?? null) : null
	);
	const runIsCancellable = $derived(
		originatingRun?.status === 'queued' || originatingRun?.status === 'running'
	);

	async function submit() {
		const trimmed = prompt.trim();
		if (trimmed.length === 0 || submitting) return;
		submitting = true;
		error = null;
		try {
			await store.promptFrom(node.id, trimmed);
			prompt = '';
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			submitting = false;
		}
	}

	async function cancelRun() {
		if (!originatingRun) return;
		try {
			await store.cancelRun(originatingRun.id);
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		}
	}
</script>

<div
	class="popover"
	style="transform: translate3d({screenX}px, {screenY}px, 0)"
	role="dialog"
	aria-label="Prompt this node"
	tabindex="-1"
	onpointerdown={(event) => event.stopPropagation()}
	onwheel={(event) => event.stopPropagation()}
>
	<form
		class="form"
		onsubmit={(event) => {
			event.preventDefault();
			void submit();
		}}
	>
		<textarea
			bind:this={textareaEl}
			class="textarea"
			rows="3"
			placeholder="Continue from this node…"
			bind:value={prompt}
			onkeydown={(event) => {
				if (event.key === 'Enter' && !event.shiftKey) {
					event.preventDefault();
					void submit();
				} else if (event.key === 'Escape') {
					event.preventDefault();
					textareaEl?.blur();
				}
			}}
		></textarea>
		<div class="row">
			<span class="hint">↵ send · ⇧↵ newline</span>
			<div class="actions">
				{#if runIsCancellable}
					<button
						type="button"
						class="btn btn--danger"
						title="Cancel running run"
						onclick={() => void cancelRun()}
					>
						Cancel run
					</button>
				{/if}
				<button
					type="submit"
					class="btn btn--primary"
					disabled={submitting || prompt.trim().length === 0}
				>
					{submitting ? 'Sending…' : 'Send'}
				</button>
			</div>
		</div>
		{#if error}
			<p class="error">{error}</p>
		{/if}
	</form>

	<TerminalOutput {store} {node} variant="compact" />
</div>

<style>
	.popover {
		position: absolute;
		top: 0;
		left: 0;
		width: min(24rem, 80vw);
		pointer-events: auto;
		/* Above .canvas-controls (z-index: 20). The popover anchors to the
		   selected node and can land under the side panel when nodes drift
		   right; keep its Send button reachable. */
		z-index: 25;
		padding: 0.55rem 0.6rem 0.55rem 0.65rem;
		display: grid;
		gap: 0.5rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 1.1rem;
		background: rgb(18 19 15 / 0.94);
		backdrop-filter: blur(18px);
		box-shadow: var(--shadow-panel);
		will-change: transform;
	}
	.form {
		display: grid;
		gap: 0.45rem;
	}
	.textarea {
		width: 100%;
		resize: none;
		border: 1px solid color-mix(in srgb, var(--color-border) 80%, transparent);
		border-radius: 0.85rem;
		background: rgb(11 12 10 / 0.92);
		padding: 0.55rem 0.7rem;
		font: inherit;
		font-size: 0.82rem;
		color: var(--color-text);
		min-height: 4rem;
	}
	.textarea:focus {
		outline: 1px solid color-mix(in srgb, var(--color-primary) 52%, transparent);
		outline-offset: 0;
	}
	.row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.4rem;
	}
	.hint {
		font-size: 0.62rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.actions {
		display: flex;
		gap: 0.4rem;
	}
	.btn {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 88%, black);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.4rem 0.75rem;
		font-size: 0.66rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
		transition:
			transform 150ms ease,
			border-color 150ms ease,
			color 150ms ease,
			opacity 150ms ease;
	}
	.btn:hover:not(:disabled) {
		transform: translateY(-1px);
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
	}
	.btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.btn--primary {
		border-color: color-mix(in srgb, var(--color-primary) 52%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 22%, rgb(18 19 15 / 1));
		color: var(--color-primary);
	}
	.btn--danger {
		color: var(--color-danger);
		border-color: color-mix(in srgb, var(--color-danger) 36%, var(--color-border));
	}
	.error {
		margin: 0;
		color: var(--color-danger);
		font-size: 0.74rem;
	}
</style>
