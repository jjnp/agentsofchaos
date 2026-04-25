import { expect, test } from '@playwright/test';

import {
	clickTab,
	createRoot,
	dragMerge,
	expectNodeCount,
	openProject,
	selectLayoutMode,
	selectNode,
	sendPrompt
} from './helpers';

// These tests build on the daemon state left behind by 01-smoke.spec.ts (the
// numeric prefix forces that ordering — Playwright walks files alphabetically).
// They run serially because the orchestrator persists project/graph state
// across browser pages, and tests that count nodes need a predictable
// starting count.
test.describe.serial('interaction', () => {
	test('graph rehydrates after page reload', async ({ page }) => {
		await openProject(page);
		await createRoot(page);
		const before = await page.locator('.agent-node').count();
		expect(before).toBeGreaterThan(0);

		// Browser reload drops the in-memory GraphStore. Re-open the project
		// and verify the daemon's persisted graph is rebuilt to the same size.
		await page.reload();
		await openProject(page);
		await expect
			.poll(() => page.locator('.agent-node').count(), { timeout: 15_000 })
			.toBeGreaterThanOrEqual(before);
	});

	test('layout mode switch toggles depth rings', async ({ page }) => {
		await openProject(page);
		await createRoot(page);

		// Make sure the graph has depth ≥ 1 so the rings layer renders something.
		// If the smoke spec already produced a child, we have depth 1 already.
		if ((await page.locator('.agent-node').count()) < 2) {
			await selectNode(page, 0);
			await sendPrompt(page, 'depth seed');
			await expectNodeCount(page, 2, 30_000);
		}

		// Rings is the default. The depth-ring layer should have at least one
		// circle once a child exists.
		await expect.poll(() => page.locator('.agent-canvas__rings circle').count())
			.toBeGreaterThanOrEqual(1);

		// Tree mode hides the depth rings entirely.
		await selectLayoutMode(page, 'Tree');
		await expect(page.locator('.agent-canvas__rings circle')).toHaveCount(0);

		// Force mode also hides them.
		await selectLayoutMode(page, 'Force');
		await expect(page.locator('.agent-canvas__rings circle')).toHaveCount(0);

		// Back to Rings — depth rings reappear.
		await selectLayoutMode(page, 'Rings');
		await expect.poll(() => page.locator('.agent-canvas__rings circle').count())
			.toBeGreaterThanOrEqual(1);
	});

	test('drag-to-merge produces an integration node', async ({ page }) => {
		await openProject(page);
		await createRoot(page);

		// Need at least two prompt children to drag together. The smoke spec
		// leaves us with one, so create one more sibling off the root.
		const startCount = await page.locator('.agent-node').count();
		if (startCount < 3) {
			await selectNode(page, 0); // re-anchor popover to the root
			await sendPrompt(page, 'sibling for merge');
			await expectNodeCount(page, startCount + 1, 30_000);
		}

		const beforeMerge = await page.locator('.agent-node').count();

		// Drag node[1] onto node[2]. With rings layout, those are the two
		// children sitting symmetrically around the root.
		await dragMerge(page, 1, 2);

		// Merge succeeded if a new node appears (count grows by 1) and the
		// canvas exposes a node tagged with the merge kind. We can't match
		// on aria-label substring "merge" — sibling prompts may include the
		// word "merge" in their titles too.
		await expectNodeCount(page, beforeMerge + 1, 30_000);
		const mergeNode = page.locator('.agent-node.kind-merge').first();
		await expect(mergeNode).toBeVisible({ timeout: 15_000 });

		// Selecting the merge node exposes the Merge tab.
		await mergeNode.dispatchEvent('click');
		await clickTab(page, 'Merge');
		await expect(page.getByText(/Merge outcome/i)).toBeVisible({ timeout: 15_000 });
		// Pin to the .label paragraphs so we don't collide with the tab
		// labels ("Output Changes Context Merge Events…").
		await expect(page.locator('.merge-report .label').filter({ hasText: 'Code merge' })).toBeVisible();
		await expect(page.locator('.merge-report .label').filter({ hasText: 'Context merge' })).toBeVisible();

		// This drag-merge produces a clean integration node so the "Resolve"
		// agent-driven resolution form should NOT render. Conflict-path
		// coverage of resolution UI lives in the backend e2e suite for now —
		// a frontend test that drives a real conflict needs a fixture that
		// sets up divergent edits, which is future work.
	});
});
