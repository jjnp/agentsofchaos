<script lang="ts">
	import type { GraphStore } from '$lib/agent-graph/state.svelte';
	import type { NodeId } from '$lib/orchestrator/contracts';

	import Button from '../primitives/Button.svelte';
	import Textarea from '../primitives/Textarea.svelte';

	interface Props {
		store: GraphStore;
		nodeId: NodeId;
	}

	let { store, nodeId }: Props = $props();

	let prompt = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);

	async function submit() {
		const trimmed = prompt.trim();
		if (trimmed.length === 0 || submitting) {
			return;
		}
		submitting = true;
		error = null;
		try {
			await store.promptFrom(nodeId, trimmed);
			prompt = '';
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			submitting = false;
		}
	}
</script>

<form
	class="prompt-form"
	onsubmit={(event) => {
		event.preventDefault();
		void submit();
	}}
>
	<Textarea
		bind:value={prompt}
		label="Prompt"
		hint="Sent to the runtime as the source of a new run."
		rows={4}
		placeholder="e.g. refactor auth middleware"
	/>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	<Button
		type="submit"
		variant="primary"
		fullWidth
		loading={submitting}
		disabled={submitting || prompt.trim().length === 0}
	>
		{submitting ? 'Submitting…' : 'Run prompt'}
	</Button>
</form>

<style>
	.prompt-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.error {
		color: var(--color-danger);
		font-size: 0.8rem;
	}
</style>
