import { describe, expect, it } from 'vitest';

import { parseUnifiedDiff, summarizeDiffTotals } from './diff';
import { sampleNodeDiff } from '$lib/components/node-diff/sample-node-diff';

describe('parseUnifiedDiff', () => {
	it('parses changed files, hunks, and totals from a unified diff', () => {
		const files = parseUnifiedDiff(sampleNodeDiff);

		expect(files).toHaveLength(2);
		expect(files[0]).toMatchObject({
			path: 'src/lib/components/Graph.svelte',
			changeType: 'modified',
			additions: 4,
			deletions: 0
		});
		expect(files[1]).toMatchObject({
			path: 'src/lib/server/graph-summary.ts',
			changeType: 'added',
			additions: 7,
			deletions: 0
		});
		expect(files[0].hunks[0]?.lines[0]).toEqual({
			type: 'context',
			content: 'export let nodes = [];'
		});

		expect(summarizeDiffTotals(files)).toEqual({ files: 2, additions: 11, deletions: 0 });
	});
});
