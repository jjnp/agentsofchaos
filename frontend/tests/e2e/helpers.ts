import { expect, type Page } from '@playwright/test';

export const E2E_REPO_PATH = '/tmp/aoc-e2e-repo';

/** Click "Open project", type the path, submit, and wait for the canvas to render. */
export async function openProject(page: Page, repoPath: string = E2E_REPO_PATH) {
	await page.goto('/');
	await expect(page.getByRole('heading', { name: /A living graph of code and context\./i }))
		.toBeVisible();
	const pathInput = page.getByRole('textbox', { name: /repository path/i });
	await pathInput.fill(repoPath);
	await page.getByRole('button', { name: /^Open project$/ }).click();
	// The opener disappears once the project is set; canvas takes over.
	await expect(page.locator('.agent-canvas')).toBeVisible({ timeout: 15_000 });
}

/** Click "New root" if no root exists; otherwise just wait for the existing node. */
export async function createRoot(page: Page) {
	const node = page.locator('.agent-node').first();
	const newRootBtn = page.getByRole('button', { name: /^New root$/ });

	// Wait until the daemon has answered the initial graph fetch — either an
	// existing node renders, or the "New root" button appears.
	await expect(node.or(newRootBtn)).toBeVisible({ timeout: 15_000 });

	if ((await page.locator('.agent-node').count()) === 0) {
		await newRootBtn.click();
		await expect(node).toBeVisible({ timeout: 15_000 });
	}
}

/** Send a prompt via the floating popover anchored to the selected node. */
export async function sendPrompt(page: Page, prompt: string) {
	const popover = page.locator('[role="dialog"][aria-label="Prompt this node"]');
	await expect(popover).toBeVisible({ timeout: 15_000 });
	const textarea = popover.locator('textarea');
	await textarea.fill(prompt);
	await popover.getByRole('button', { name: /^Send$/ }).click();
}

/** Resolve when the canvas shows at least `n` nodes. */
export async function expectNodeCount(page: Page, n: number, timeoutMs = 15_000) {
	await expect
		.poll(() => page.locator('.agent-node').count(), { timeout: timeoutMs })
		.toBeGreaterThanOrEqual(n);
}

/** Click on a tab in the inspector. */
export async function clickTab(page: Page, name: 'Output' | 'Changes' | 'Context' | 'Merge' | 'Events') {
	await page.getByRole('tab', { name: new RegExp(`^${name}`) }).click();
}
