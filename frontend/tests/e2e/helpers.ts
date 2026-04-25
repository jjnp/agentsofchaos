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
export async function clickTab(
	page: Page,
	name: 'Output' | 'Changes' | 'Context' | 'Merge' | 'Artifacts' | 'Events'
) {
	await page.getByRole('tab', { name: new RegExp(`^${name}`) }).click();
}

/** Programmatically click an SVG node (avoids the popover overlay). */
export async function selectNode(page: Page, index: number) {
	await page.locator('[data-agent-node-id]').nth(index).dispatchEvent('click');
}

/**
 * Drag-to-merge the SVG node at `sourceIndex` onto the one at `targetIndex`.
 * Uses the real mouse pipeline so the canvas's pointer-capture / pointermove /
 * pointerup wiring runs exactly as it does in production.
 */
export async function dragMerge(page: Page, sourceIndex: number, targetIndex: number) {
	const nodes = page.locator('[data-agent-node-id]');
	const source = await nodes.nth(sourceIndex).boundingBox();
	const target = await nodes.nth(targetIndex).boundingBox();
	if (!source || !target) {
		throw new Error(
			`drag-merge: missing bounding box (source=${source ? 'ok' : 'null'}, target=${target ? 'ok' : 'null'})`
		);
	}
	await dragMergeBetween(page, source, target);
}

/** Same as dragMerge but you supply pre-located source/target locators. */
export async function dragMergeLocators(
	page: Page,
	source: ReturnType<Page['locator']>,
	target: ReturnType<Page['locator']>
) {
	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) {
		throw new Error('drag-merge: missing bounding box');
	}
	await dragMergeBetween(page, sourceBox, targetBox);
}

async function dragMergeBetween(
	page: Page,
	source: { x: number; y: number; width: number; height: number },
	target: { x: number; y: number; width: number; height: number }
) {
	const sx = source.x + source.width / 2;
	const sy = source.y + source.height / 2;
	const tx = target.x + target.width / 2;
	const ty = target.y + target.height / 2;

	await page.mouse.move(sx, sy);
	await page.mouse.down();
	// Step the move so pointermove fires multiple times — the canvas tracks
	// mergeHover via document.elementFromPoint on each move event.
	await page.mouse.move((sx + tx) / 2, (sy + ty) / 2, { steps: 10 });
	await page.mouse.move(tx, ty, { steps: 10 });
	await page.mouse.up();
}

/** Click a side-controls layout-mode button by its visible label. */
export async function selectLayoutMode(page: Page, mode: 'Rings' | 'Tree' | 'Force') {
	await page.getByRole('button', { name: new RegExp(`^${mode}$`) }).click();
}
