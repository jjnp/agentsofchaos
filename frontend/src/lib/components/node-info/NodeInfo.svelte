<script lang="ts">
	import NodeDiffViewer from '$lib/components/node-diff/NodeDiffViewer.svelte';
	import PiSummaryView from '$lib/components/pi-summary/PiSummaryView.svelte';

	interface NodeInfoData {
		id: string;
		title: string;
		status: string;
		prompt: string;
		diff: string;
		context?: string;
		summary: string;
	}

	interface Props {
		node: NodeInfoData;
	}

	let { node }: Props = $props();
</script>

<section class="flex flex-col gap-4">
	<div class="panel p-6">
		<div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
			<div>
				<p class="text-sm font-medium tracking-[0.18em] text-primary-accent uppercase">
					Selected node
				</p>
				<h2 class="mt-2 text-2xl font-semibold text-text">{node.title}</h2>
				<p class="mt-3 max-w-4xl text-sm leading-7 text-text-muted">{node.prompt}</p>
			</div>
			<div class="flex items-start gap-3">
				<span
					class={`rounded-full px-2 py-1 text-[11px] uppercase ${node.status === 'active' ? 'bg-primary/15 text-primary' : 'bg-surface-elevated text-text-muted'}`}
				>
					{node.status}
				</span>
				<div
					class="rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm text-text-muted"
				>
					<div>Node ID</div>
					<div class="mt-1 font-mono text-text">{node.id}</div>
				</div>
			</div>
		</div>
	</div>

	<PiSummaryView summary={node.summary} label="Pi summary" />

	<NodeDiffViewer nodeId={node.id} prompt={node.prompt} diff={node.diff} context={node.context} />
</section>
