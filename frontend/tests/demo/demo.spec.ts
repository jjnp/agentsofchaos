/**
 * Demo recording (NOT a regression test).
 *
 * This spec is deliberately paced and visual — it walks through the
 * canonical graph-native flow so the resulting video can be turned
 * into a README gif. Run it with `npx playwright test --config
 * playwright.demo.config.ts` to opt into video recording at the right
 * resolution; it is excluded from the default test:e2e run because
 * its pauses make it slow.
 */

import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';

const DEMO_REPO = '/tmp/aoc-demo-repo';

function ensureFreshRepo(path: string) {
	if (existsSync(path)) rmSync(path, { recursive: true, force: true });
	mkdirSync(path, { recursive: true });
	writeFileSync(`${path}/README.md`, '# demo fixture\n');
	const env = {
		...process.env,
		GIT_AUTHOR_NAME: 'demo',
		GIT_AUTHOR_EMAIL: 'demo@aoc.local',
		GIT_COMMITTER_NAME: 'demo',
		GIT_COMMITTER_EMAIL: 'demo@aoc.local'
	};
	execSync('git init -q -b main', { cwd: path, env, stdio: 'pipe' });
	execSync('git add README.md', { cwd: path, env, stdio: 'pipe' });
	execSync('git commit -q -m init', { cwd: path, env, stdio: 'pipe' });
}

const beat = (ms = 600) => new Promise((r) => setTimeout(r, ms));

test('graph-native demo: root → prompts → drag-merge → conflicted → resolve', async ({
	page
}) => {
	test.setTimeout(120_000);
	ensureFreshRepo(DEMO_REPO);

	await page.goto('/');
	await beat();

	// 1) Open the project
	const pathInput = page.getByRole('textbox', { name: /repository path/i });
	await pathInput.fill(DEMO_REPO);
	await beat(400);
	await page.getByRole('button', { name: /^Open project$/ }).click();
	await expect(page.locator('.agent-canvas')).toBeVisible({ timeout: 15_000 });
	await beat(800);

	// 2) Create the root from HEAD
	await page.getByRole('button', { name: /^New root$/ }).click();
	await expect(page.locator('.agent-node').first()).toBeVisible();
	await beat(900);

	// 3) Prompt the root → seed conflict.txt so the branches share an ancestor
	const popover = page.locator('[role="dialog"][aria-label="Prompt this node"]');
	await expect(popover).toBeVisible();
	await popover.locator('textarea').type('plan.txt:initial design notes', {
		delay: 35
	});
	await beat(400);
	await popover.getByRole('button', { name: /^Send$/ }).click();
	await expect.poll(() => page.locator('.agent-node').count()).toBeGreaterThanOrEqual(2);
	await beat(900);

	// 4) Branch A — re-anchor to the seed and prompt
	await page.locator('[data-agent-node-id]').nth(1).dispatchEvent('click');
	await expect(popover).toBeVisible();
	await beat(300);
	await popover.locator('textarea').type('plan.txt:local daemon first', {
		delay: 35
	});
	await beat(400);
	await popover.getByRole('button', { name: /^Send$/ }).click();
	await expect.poll(() => page.locator('.agent-node').count()).toBeGreaterThanOrEqual(3);
	await beat(900);

	// 5) Branch B — different version of the same file → real conflict
	await page.locator('[data-agent-node-id]').nth(1).dispatchEvent('click');
	await expect(popover).toBeVisible();
	await beat(300);
	await popover.locator('textarea').type('plan.txt:hosted plane first', {
		delay: 35
	});
	await beat(400);
	await popover.getByRole('button', { name: /^Send$/ }).click();
	await expect.poll(() => page.locator('.agent-node').count()).toBeGreaterThanOrEqual(4);
	await beat(1200);

	// 6) Recenter and switch layout to make the next move legible
	await page
		.getByRole('button', { name: /^Recenter$/ })
		.dispatchEvent('click');
	await beat(700);

	// 7) Drag-merge branch A onto branch B (the canonical graph-native gesture)
	await page.locator('[data-agent-node-id]').first().dispatchEvent('click');
	await beat(300);
	const sourceNode = page.locator(
		'[data-agent-node-id][aria-label*="local daemon first"]'
	);
	const targetNode = page.locator(
		'[data-agent-node-id][aria-label*="hosted plane first"]'
	);
	const source = await sourceNode.boundingBox();
	const target = await targetNode.boundingBox();
	if (source && target) {
		const sx = source.x + source.width / 2;
		const sy = source.y + source.height / 2;
		const tx = target.x + target.width / 2;
		const ty = target.y + target.height / 2;
		await page.mouse.move(sx, sy);
		await page.mouse.down();
		await page.mouse.move((sx + tx) / 2, (sy + ty) / 2, { steps: 22 });
		await beat(250);
		await page.mouse.move(tx, ty, { steps: 22 });
		await beat(250);
		await page.mouse.up();
	}
	await expect.poll(() => page.locator('.agent-node').count()).toBeGreaterThanOrEqual(5);
	await beat(1500);

	// 8) Inspect the conflicted merge node — Merge tab shows code + context
	const mergeNode = page.locator('.agent-node.kind-merge').first();
	await expect(mergeNode).toBeVisible({ timeout: 15_000 });
	await mergeNode.dispatchEvent('click');
	await beat(700);
	await page.getByRole('tab', { name: /^Merge/ }).click();
	await expect(page.getByText(/Merge outcome/i)).toBeVisible({ timeout: 10_000 });
	await beat(2000);

	// 9) Type a resolution prompt — agent-driven, but here noop fixture mode
	const resolveForm = page.locator('.merge-report .resolve-form');
	await expect(resolveForm).toBeVisible({ timeout: 10_000 });
	await resolveForm
		.locator('textarea')
		.type('plan.txt:local daemon first, hosted plane v2', {
			delay: 30
		});
	await beat(700);
	await resolveForm.getByRole('button', { name: /^Resolve$/ }).click();
	await expect.poll(() => page.locator('.agent-node').count()).toBeGreaterThanOrEqual(6);
	await beat(1500);

	// 10) Open the new RESOLUTION node's Artifacts tab — closes the loop
	const resolutionNode = page.locator('.agent-node.kind-resolution').first();
	await expect(resolutionNode).toBeVisible({ timeout: 10_000 });
	await resolutionNode.dispatchEvent('click');
	await beat(700);
	await page.getByRole('tab', { name: /^Artifacts/ }).click();
	await expect(
		page.locator('.artifacts .row .kind').filter({ hasText: 'resolution_report' })
	).toBeVisible({ timeout: 10_000 });
	await beat(2200);
});
