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

<section class="flex flex-col gap-3">
	<div class="panel p-4">
		<div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
			<div class="min-w-0">
				<p class="text-[10px] font-medium tracking-[0.22em] text-primary-accent uppercase">
					Selected node
				</p>
				<h2 class="mt-1 text-lg font-semibold text-text sm:text-xl">{node.title}</h2>
				<p class="mt-2 max-w-3xl text-xs leading-5 text-text-muted sm:text-sm sm:leading-6">
					{node.prompt}
				</p>
			</div>
			<div class="flex flex-wrap items-start gap-2.5">
				<span
					class={`rounded-full px-2 py-0.5 text-[10px] font-medium tracking-[0.14em] uppercase ${node.status === 'active' ? 'bg-primary/15 text-primary' : 'bg-surface-elevated text-text-muted'}`}
				>
					{node.status}
				</span>
				<div
					class="max-w-[14rem] rounded-xl border border-border bg-surface/70 px-3 py-2 text-[11px] leading-4 text-text-muted"
				>
					<div class="tracking-[0.12em] uppercase">Node ID</div>
					<div class="mt-1 font-mono text-[11px] break-all text-text">{node.id}</div>
				</div>
			</div>
		</div>
	</div>

	<PiSummaryView summary={node.summary} label="Pi summary" />

	<NodeDiffViewer nodeId={node.id} prompt={node.prompt} diff={node.diff} context={node.context} />
</section>
