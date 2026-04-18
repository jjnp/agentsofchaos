import { describe, expect, it } from 'vitest';

import { parsePiSummary } from './parse';
import { samplePiSummary } from '$lib/components/pi-summary/sample-pi-summary';

describe('parsePiSummary', () => {
	it('parses titled sections and progress steps from summary markdown', () => {
		const document = parsePiSummary(samplePiSummary);

		expect(document.title).toBe('Node Review Summary');
		expect(document.sections.map((section) => section.title)).toEqual([
			'User intent',
			'What was implemented',
			'Progress steps',
			'Why this matters',
			'Open questions',
			'Suggested next step'
		]);

		const progressSection = document.sections.find((section) => section.title === 'Progress steps');
		expect(progressSection?.blocks[0]).toMatchObject({ type: 'progress-steps' });
		expect(progressSection?.blocks[0]?.steps).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					label: 'Built a reusable node diff viewer component.',
					status: 'done'
				}),
				expect.objectContaining({
					label: 'Wire the node inspector to real graph-node metadata from an API endpoint.',
					status: 'pending'
				})
			])
		);
	});
});
