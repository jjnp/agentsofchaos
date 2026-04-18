import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';

import NodeDiffViewer from './NodeDiffViewer.svelte';
import { sampleNodeDiff, sampleNodePrompt } from './sample-node-diff';
import { parseUnifiedDiff, summarizeDiffTotals } from '$lib/features/node-diff/diff';

describe('NodeDiffViewer', () => {
	it('renders a compact file navigator and lazily loads a per-file summary', async () => {
		const files = parseUnifiedDiff(sampleNodeDiff);
		const { getByRole, getByText } = await render(NodeDiffViewer, {
			props: {
				prompt: sampleNodePrompt,
				diff: sampleNodeDiff,
				overviewLoader: async () => ({
					prompt: sampleNodePrompt,
					overallSummary: 'Overview ready.',
					overallSummaryCached: true,
					files,
					totals: summarizeDiffTotals(files)
				}),
				fileSummaryLoader: async ({ file }) => ({
					path: file.path,
					summary: `Summary for ${file.path}`,
					cached: true
				})
			}
		});

		await expect.element(getByText('Change totals')).toBeInTheDocument();
		await expect.element(getByText('src/lib', { exact: true })).toBeInTheDocument();
		await expect
			.element(getByRole('button', { name: 'src/lib/components/Graph.svelte' }))
			.toBeInTheDocument();
		await expect
			.element(getByRole('button', { name: 'src/lib/server/graph-summary.ts' }))
			.toBeInTheDocument();
		await getByRole('button', { name: 'Load file summary' }).click();
		await expect
			.element(getByText('Summary for src/lib/components/Graph.svelte'))
			.toBeInTheDocument();
	});
});
