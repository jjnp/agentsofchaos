<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';

	interface Props {
		store: GraphStore;
	}

	let { store }: Props = $props();

	let path = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);

	async function submit() {
		const trimmed = path.trim();
		if (trimmed.length === 0 || submitting) {
			return;
		}
		submitting = true;
		error = null;
		try {
			await store.openProject(trimmed);
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			submitting = false;
		}
	}
</script>

<section class="opener">
	<header>
		<p class="eyebrow">Orchestrator graph</p>
		<h1>A living graph of code and context.</h1>
		<p class="copy">
			Point the daemon at a local git repository on the machine running
			<code>orchestrator</code>. Opens are idempotent — re-opening the same path picks up the
			existing graph.
		</p>
	</header>

	<form
		class="form"
		onsubmit={(event) => {
			event.preventDefault();
			void submit();
		}}
	>
		<label class="field">
			<span class="label">Repository path</span>
			<input
				class="input"
				type="text"
				bind:value={path}
				placeholder="/home/J3/agentsofchaos"
				autocomplete="off"
				spellcheck={false}
			/>
		</label>

		{#if error}
			<p class="error">{error}</p>
		{/if}

		<button type="submit" class="btn primary" disabled={submitting || path.trim().length === 0}>
			{submitting ? 'Opening…' : 'Open project'}
		</button>
	</form>

	<footer>
		<p class="hint">
			Tip on this VM: <code>/tmp/aoc-smoke-repo</code> is a 1-commit fixture, and
			<code>/home/J3/agentsofchaos</code> is the real repo.
		</p>
	</footer>
</section>

<style>
	.opener {
		width: min(40rem, calc(100vw - 3rem));
		display: grid;
		gap: 1.5rem;
		padding: 2rem 2.2rem 1.6rem;
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		border-radius: 1.6rem;
		background: rgb(18 19 15 / 0.9);
		backdrop-filter: blur(18px);
		box-shadow: var(--shadow-panel);
	}
	header {
		display: grid;
		gap: 0.5rem;
	}
	.eyebrow {
		font-size: 0.68rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	h1 {
		font-size: 1.65rem;
		font-weight: 600;
		color: var(--color-text);
		line-height: 1.2;
	}
	.copy {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		line-height: 1.55;
		max-width: 32rem;
	}
	code {
		font-family: var(--font-mono);
		font-size: 0.82em;
		padding: 0.1rem 0.35rem;
		border-radius: 0.3rem;
		background: var(--color-surface-elevated);
	}
	.form {
		display: grid;
		gap: 0.85rem;
	}
	.field {
		display: grid;
		gap: 0.4rem;
	}
	.label {
		font-size: 0.68rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}
	.input {
		width: 100%;
		border: 1px solid color-mix(in srgb, var(--color-border) 84%, transparent);
		border-radius: 1rem;
		background: rgb(11 12 10 / 0.92);
		padding: 0.95rem 1.1rem;
		font: inherit;
		font-family: var(--font-mono);
		font-size: 0.9rem;
		color: var(--color-text);
	}
	.input:focus {
		outline: 1px solid color-mix(in srgb, var(--color-primary) 52%, transparent);
		outline-offset: 0;
	}
	.btn {
		border: 1px solid color-mix(in srgb, var(--color-border) 82%, transparent);
		background: color-mix(in srgb, var(--color-surface-elevated) 88%, black);
		color: var(--color-text);
		border-radius: 999px;
		padding: 0.85rem 1.2rem;
		font-size: 0.78rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		cursor: pointer;
		transition:
			transform 180ms ease,
			border-color 180ms ease,
			color 180ms ease,
			opacity 180ms ease;
		justify-self: end;
	}
	.btn:hover:not(:disabled) {
		transform: translateY(-1px);
		border-color: color-mix(in srgb, var(--color-primary) 44%, var(--color-border));
	}
	.btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.btn.primary {
		border-color: color-mix(in srgb, var(--color-primary) 52%, var(--color-border));
		background: color-mix(in srgb, var(--color-primary) 22%, rgb(18 19 15 / 1));
		color: var(--color-primary);
	}
	.error {
		color: var(--color-danger);
		font-size: 0.85rem;
	}
	footer .hint {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}
</style>
