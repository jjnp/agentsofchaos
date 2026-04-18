import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';

import PiSummaryView from './PiSummaryView.svelte';
import { samplePiSummary } from './sample-pi-summary';

describe('PiSummaryView', () => {
	it('renders parsed sections and progress steps', async () => {
		const { getByText } = await render(PiSummaryView, {
			props: { summary: samplePiSummary }
		});

		await expect.element(getByText('Node Review Summary')).toBeInTheDocument();
		await expect.element(getByText('User intent')).toBeInTheDocument();
		await expect
			.element(getByText('Built a reusable node diff viewer component.'))
			.toBeInTheDocument();
		await expect
			.element(
				getByText('Wire the node inspector to real graph-node metadata from an API endpoint.')
			)
			.toBeInTheDocument();
	});
});
