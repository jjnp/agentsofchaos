import { expect, test } from '@playwright/test';

import { clickTab, createRoot, expectNodeCount, openProject, sendPrompt } from './helpers';

// One linear walk through the demo path. The daemon keeps state across tests
// (idempotent project, single root per project), so isolating each assertion
// in its own `test()` would either need teardown or duplicate work. A single
// scripted run is honest about what we're verifying.
test('full demo path: open → root → prompt → child → tabs', async ({ page }) => {
	test.setTimeout(60_000);

	await test.step('open project', async () => {
		await openProject(page);
	});

	await test.step('create root', async () => {
		await createRoot(page);
		await expectNodeCount(page, 1);
	});

	await test.step('events tab carries the topic feed', async () => {
		await page.locator('.agent-node').first().click();
		await clickTab(page, 'Events');
		// Feed is opt-in — rendering 200 keyed list items on every push
		// was the perf hot spot under sustained agent runs. Enable it
		// explicitly, then the topic list should populate.
		await page.getByRole('button', { name: /^Enable event feed$/ }).click();
		await expect(page.getByText('project_opened')).toBeVisible({ timeout: 10_000 });
		await expect(page.getByText('root_node_created')).toBeVisible();
	});

	await test.step('changes tab loads the diff against empty tree', async () => {
		await clickTab(page, 'Changes');
		// README.md appears twice: once in the file list, once as the selected
		// file heading. Pin to the heading.
		await expect(page.getByRole('heading', { name: /README\.md/ })).toBeVisible({
			timeout: 15_000
		});
		await expect(page.getByText('files', { exact: true })).toBeVisible();
	});

	await test.step('prompt the root and watch the child appear', async () => {
		await sendPrompt(page, 'first prompt');
		await expectNodeCount(page, 2, 30_000);
	});

	await test.step('output tab shows runtime events on the child', async () => {
		// The popover sits over the currently-selected node, so a real mouse
		// click at the child's center can land on the popover. Dispatch the
		// click event directly on the SVG node element instead.
		await page.locator('[data-agent-node-id]').nth(1).dispatchEvent('click');
		await clickTab(page, 'Output');
		const terminalLine = page.locator('.line--info, .line--error').first();
		await expect(terminalLine).toBeVisible({ timeout: 30_000 });
	});
});
