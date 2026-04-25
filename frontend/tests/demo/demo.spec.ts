/**
 * Demo recording (NOT a regression test).
 *
 * Drives the *real* pi runtime through the canonical flow so the gif
 * shows real LLM work, not the deterministic noop fixture.
 *
 * Graph shape (linear → fork): root → seed → {branchA, branchB}.
 * Branches are children of the seed (the basic game), not of the root.
 * That keeps root at the top of the rings layout — when we anchor the
 * popover to root before the drag, it's far from the drag targets at
 * the bottom of the canvas.
 *
 * Flow:
 *   1. Open project, create root from HEAD
 *   2. Prompt the root → "tic tac toe in JS for the CLI" (creates seed)
 *   3. From seed, prompt: "add a 3-player mode" (branchA)
 *   4. From seed, prompt: "add a random move AI opponent" (branchB)
 *   5. Drag-merge branchA onto branchB
 *   6. Tour every tab on the merge node
 *   7. Zoom out to show the whole graph
 *
 * Run with: `npx playwright test --config playwright.demo.config.ts`.
 * Wall clock is dominated by the LLM — expect 10–15 min total.
 */

import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';

const DEMO_REPO = '/tmp/aoc-demo-repo';
const RUN_TIMEOUT_MS = 600_000; // 10 min per run — pi+OpenAI can be slow

function ensureFreshRepo(path: string) {
	if (existsSync(path)) rmSync(path, { recursive: true, force: true });
	mkdirSync(path, { recursive: true });
	writeFileSync(`${path}/README.md`, '# tic tac toe demo\n');
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

test('graph-native demo: tic tac toe → 3-player → AI opponent → merge', async ({ page }) => {
	test.setTimeout(1_800_000);
	ensureFreshRepo(DEMO_REPO);

	// Surface run lifecycle in the test log so we can tell "still working"
	// from "actually stuck" while the recording is going.
	page.on('console', (msg) => {
		const text = msg.text();
		if (/\[net\]|run|node|merge/i.test(text)) {
			console.log(`[browser] ${text}`);
		}
	});

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

	// 3) Prompt the root → write the game. Prompts are written so the
	//    first ~32 chars (which become the node title via
	//    `_default_child_title`) carry a distinguishing prefix the
	//    Playwright spec can match by aria-label later.
	const popover = page.locator('[role="dialog"][aria-label="Prompt this node"]');
	await expect(popover).toBeVisible();
	await popover.locator('textarea').type(
		'Tic tac toe in JS: write tictactoe.js, a simple two-player CLI game (moves like "1 2" for row/col).',
		{ delay: 25 }
	);
	await beat(400);
	await popover.getByRole('button', { name: /^Send$/ }).click();
	await waitForNodeCount(page, 2, RUN_TIMEOUT_MS);
	await beat(1200);

	// Show off the freshly-landed node — every tab gets a beat so the
	// gif viewer can read each one.
	const seedNode = page.locator('[data-agent-node-id][aria-label*="Tic tac toe"]').first();
	await tourTabsOn(page, seedNode, ['Output', 'Changes', 'Context', 'Events']);

	// 4) Branch A — re-anchor to the seed and prompt for 3-player mode.
	//    Branches are children of the seed (which already has
	//    tictactoe.js) so the merge has a real common ancestor with the
	//    file in it.
	await seedNode.dispatchEvent('click');
	await expect(popover).toBeVisible();
	await beat(400);
	await popover
		.locator('textarea')
		.type('3-player mode: modify tictactoe.js to support 3 players (X, O, Δ) on a 5x5 board.', {
			delay: 25
		});
	await beat(400);
	await popover.getByRole('button', { name: /^Send$/ }).click();
	await waitForNodeCount(page, 3, RUN_TIMEOUT_MS);
	// Give the daemon a moment to flush the run's final artifacts and
	// the node's `ready` status. The node materialises the moment the
	// run commits, but downstream consumers (merge classifier) want
	// the run-state transition to settle.
	await beat(1500);
	const branchA = page.locator('[data-agent-node-id][aria-label*="3-player mode"]').first();
	await tourTabsOn(page, branchA, ['Output', 'Changes', 'Context']);

	// 5) Branch B — re-anchor to the seed, ask for a random AI opponent
	await seedNode.dispatchEvent('click');
	await expect(popover).toBeVisible();
	await beat(400);
	await popover
		.locator('textarea')
		.type(
			'Random AI opponent: modify tictactoe.js so player 2 picks a uniformly random legal move.',
			{ delay: 25 }
		);
	await beat(400);
	await popover.getByRole('button', { name: /^Send$/ }).click();
	await waitForNodeCount(page, 4, RUN_TIMEOUT_MS);
	await beat(1500);
	const branchB = page.locator('[data-agent-node-id][aria-label*="Random AI"]').first();
	await tourTabsOn(page, branchB, ['Output', 'Changes', 'Context']);

	// 6) Recenter, then anchor the popover at root so it sits at the
	//    top of the canvas — clear of the drag targets at the bottom.
	//    (Same trick the resolution e2e test uses.)
	await page.getByRole('button', { name: /^Recenter$/ }).dispatchEvent('click');
	await beat(900);
	await page.locator('[data-agent-node-id]').first().dispatchEvent('click');
	await beat(400);

	// 7) Drag-merge branch A onto branch B. Both touch tictactoe.js in
	//    different ways — the merge may be clean or code_conflicted;
	//    the demo treats both outcomes as success.
	await expect(branchA).toBeInViewport({ timeout: 5_000 });
	await expect(branchB).toBeInViewport({ timeout: 5_000 });
	const sourceBox = await branchA.boundingBox();
	const targetBox = await branchB.boundingBox();
	if (sourceBox && targetBox) {
		const sx = sourceBox.x + sourceBox.width / 2;
		const sy = sourceBox.y + sourceBox.height / 2;
		const tx = targetBox.x + targetBox.width / 2;
		const ty = targetBox.y + targetBox.height / 2;
		await page.mouse.move(sx, sy);
		await page.mouse.down();
		await page.mouse.move((sx + tx) / 2, (sy + ty) / 2, { steps: 22 });
		await beat(300);
		await page.mouse.move(tx, ty, { steps: 22 });
		await beat(300);
		await page.mouse.up();
	}
	await waitForNodeCount(page, 5, 60_000);
	await beat(1500);

	// 8) Walk through every tab on the merge node — Merge tab is the
	//    headline; Changes shows the integrated diff; Artifacts surfaces
	//    the merge report.
	const mergeNode = page.locator('.agent-node.kind-merge').first();
	await expect(mergeNode).toBeVisible({ timeout: 15_000 });
	await mergeNode.dispatchEvent('click');
	await beat(700);
	for (const tab of ['Output', 'Changes', 'Context', 'Merge', 'Artifacts', 'Events'] as const) {
		const button = page.getByRole('tab', { name: new RegExp(`^${tab}`) });
		if (await button.count()) {
			await button.first().click();
			await beat(1300);
		}
	}

	// 9) Zoom out to the full graph. The canvas only supports wheel
	//    zoom (minScale 0.5) — fire several outward wheel events at the
	//    canvas centre, then Recenter to frame the result.
	const canvas = page.locator('.agent-canvas').first();
	const canvasBox = await canvas.boundingBox();
	if (canvasBox) {
		const cx = canvasBox.x + canvasBox.width / 2;
		const cy = canvasBox.y + canvasBox.height / 2;
		await page.mouse.move(cx, cy);
		for (let i = 0; i < 8; i++) {
			await page.mouse.wheel(0, 280);
			await beat(120);
		}
	}
	await beat(700);
	await page.getByRole('button', { name: /^Recenter$/ }).dispatchEvent('click');
	await beat(2400);
});

/**
 * Poll for at least `n` nodes on the canvas, clicking the side-panel
 * "Refresh" button between checks so we don't depend on the SSE event
 * stream alone. Pi runs are long-lived (60–90s of LLM work) and the
 * SSE connection sometimes silently misses the trailing
 * `prompt_node_created` event — refreshing forces a clean GET /graph.
 */
async function waitForNodeCount(
	page: import('@playwright/test').Page,
	n: number,
	timeoutMs: number
): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	const refresh = page.getByRole('button', { name: /^Refresh$/ });
	while (Date.now() < deadline) {
		const count = await page.locator('.agent-node').count();
		if (count >= n) return;
		// dispatchEvent so the popover (z-index 25) doesn't eat the click.
		await refresh.first().dispatchEvent('click').catch(() => {});
		await new Promise((r) => setTimeout(r, 2_500));
	}
	const got = await page.locator('.agent-node').count();
	throw new Error(`waited ${timeoutMs}ms for ${n} nodes, got ${got}`);
}

/**
 * Click each tab on the inspector for the given node locator, with a
 * beat between clicks so the gif viewer can register each one. Skips
 * tabs that don't exist (e.g. Merge on a non-merge node).
 */
async function tourTabsOn(
	page: import('@playwright/test').Page,
	node: ReturnType<import('@playwright/test').Page['locator']>,
	tabs: ReadonlyArray<'Output' | 'Changes' | 'Context' | 'Merge' | 'Artifacts' | 'Events'>
) {
	await node.dispatchEvent('click');
	await beat(700);
	for (const tab of tabs) {
		const button = page.getByRole('tab', { name: new RegExp(`^${tab}`) });
		if (await button.count()) {
			await button.first().click();
			await beat(1100);
		}
	}
}
