<script lang="ts">
	import DiffFileList from './DiffFileList.svelte';
	import DiffFileView from './DiffFileView.svelte';
	import type {
		FileSummaryResponse,
		NodeDiffOverview,
		NodeDiffOverviewRequest,
		FileSummaryRequest
	} from '$lib/features/node-diff/schemas';

	type OverviewLoader = (input: NodeDiffOverviewRequest) => Promise<NodeDiffOverview>;
	type FileSummaryLoader = (input: FileSummaryRequest) => Promise<FileSummaryResponse>;

	interface Props {
		nodeId?: string;
		prompt: string;
		diff: string;
		context?: string;
		overviewLoader?: OverviewLoader;
		fileSummaryLoader?: FileSummaryLoader;
	}

	interface FileSummaryState {
		summary: string;
		cached: boolean;
	}

	async function postJson<TRequest, TResponse>(url: string, body: TRequest) {
		const response = await fetch(url, {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify(body)
		});

		if (!response.ok) {
			throw new Error(`Request failed with status ${response.status}`);
		}

		return (await response.json()) as TResponse;
	}

	const defaultOverviewLoader: OverviewLoader = async (input) =>
		postJson<NodeDiffOverviewRequest, NodeDiffOverview>('/api/node-diff', input);
	const defaultFileSummaryLoader: FileSummaryLoader = async (input) =>
		postJson<FileSummaryRequest, FileSummaryResponse>('/api/node-diff/file-summary', input);

	let {
		nodeId,
		prompt,
		diff,
		context,
		overviewLoader = defaultOverviewLoader,
		fileSummaryLoader = defaultFileSummaryLoader
	}: Props = $props();

	let overview = $state<NodeDiffOverview | null>(null);
	let loadingOverview = $state(true);
	let overviewError = $state<string | null>(null);
	let selectedPath = $state<string | null>(null);
	let fileSummaries = $state<Record<string, FileSummaryState>>({});
	let summaryLoadingPath = $state<string | null>(null);
	let summaryErrors = $state<Record<string, string>>({});

	const selectedFile = $derived(overview?.files.find((file) => file.path === selectedPath) ?? null);
	const selectedFileSummary = $derived(
		selectedFile ? (fileSummaries[selectedFile.path] ?? null) : null
	);

	async function loadOverview() {
		loadingOverview = true;
		overviewError = null;
		try {
			overview = await overviewLoader({ nodeId, prompt, diff, context });
			selectedPath = overview.files[0]?.path ?? null;
		} catch (error) {
			overviewError = error instanceof Error ? error.message : 'Failed to load diff overview.';
		} finally {
			loadingOverview = false;
		}
	}

	async function loadFileSummary() {
		if (!selectedFile) return;
		summaryLoadingPath = selectedFile.path;
		summaryErrors = { ...summaryErrors, [selectedFile.path]: '' };
		try {
			const response = await fileSummaryLoader({
				nodeId,
				prompt,
				context,
				file: selectedFile
			});
			fileSummaries = {
				...fileSummaries,
				[response.path]: {
					summary: response.summary,
					cached: response.cached
				}
			};
		} catch (error) {
			summaryErrors = {
				...summaryErrors,
				[selectedFile.path]: error instanceof Error ? error.message : 'Failed to load file summary.'
			};
		} finally {
			summaryLoadingPath = null;
		}
	}

	let lastRequestKey = $state('');
	$effect(() => {
		const requestKey = JSON.stringify({ nodeId, prompt, diff, context });
		if (requestKey === lastRequestKey) return;
		lastRequestKey = requestKey;
		fileSummaries = {};
		summaryErrors = {};
		void loadOverview();
	});
</script>

<section class="flex min-h-[30rem] flex-col gap-3">
	{#if loadingOverview}
		<section
			class="rounded-3xl border border-border bg-surface/70 p-5 text-xs text-text-muted sm:text-sm"
		>
			Loading node diff overview…
		</section>
	{:else if overviewError}
		<section class="rounded-3xl border border-danger/40 bg-danger/10 p-8">
			<p class="text-sm text-danger">{overviewError}</p>
			<button
				type="button"
				class="mt-4 rounded-full border border-danger/40 px-3 py-1.5 text-sm text-danger"
				onclick={loadOverview}
			>
				Retry
			</button>
		</section>
	{:else if overview}
		<div class="grid gap-4 lg:grid-cols-[17rem_minmax(0,1fr)]">
			<aside class="flex min-h-0 flex-col gap-3">
				<section class="rounded-2xl border border-border bg-surface/80 p-3.5">
					<h3 class="text-[11px] font-semibold tracking-[0.18em] text-text uppercase">
						Change totals
					</h3>
					<div class="mt-2.5 grid grid-cols-3 gap-2.5 text-center text-xs sm:text-sm">
						<div class="rounded-2xl bg-surface-elevated px-3 py-3">
							<div class="text-lg font-semibold text-text">{overview.totals.files}</div>
							<div class="text-text-muted">Files</div>
						</div>
						<div class="rounded-2xl bg-emerald-400/10 px-3 py-3">
							<div class="text-lg font-semibold text-emerald-100">+{overview.totals.additions}</div>
							<div class="text-text-muted">Added</div>
						</div>
						<div class="rounded-2xl bg-rose-400/10 px-3 py-3">
							<div class="text-lg font-semibold text-rose-100">-{overview.totals.deletions}</div>
							<div class="text-text-muted">Removed</div>
						</div>
					</div>
				</section>

				<section class="min-h-0 rounded-2xl border border-border bg-surface/80 p-3">
					<div class="mb-2.5 flex items-center justify-between gap-3 px-1">
						<h3 class="text-[11px] font-semibold tracking-[0.18em] text-text uppercase">
							Changed files
						</h3>
						<span class="text-xs text-text-muted">{overview.files.length}</span>
					</div>
					<DiffFileList
						files={overview.files}
						{selectedPath}
						onSelect={(path) => (selectedPath = path)}
					/>
				</section>
			</aside>

			<div class="min-h-0">
				<DiffFileView
					file={selectedFile}
					summary={selectedFileSummary?.summary ?? null}
					summaryLoading={selectedFile ? summaryLoadingPath === selectedFile.path : false}
					summaryError={selectedFile ? (summaryErrors[selectedFile.path] ?? null) : null}
					summaryCached={selectedFileSummary?.cached ?? false}
					onRequestSummary={loadFileSummary}
				/>
			</div>
		</div>
	{/if}
</section>
