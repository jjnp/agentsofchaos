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
 *   1. Open project — the orchestrator now auto-creates the root from
 *      HEAD as part of `POST /projects/open`, so the spec just waits
 *      for the root to render and clicks it to open the prompt popover
 *   2. Prompt the root → "tic tac toe in JS for the CLI" (creates seed)
 *   3. From seed, fork branchA: "add a 3-player mode" — DO NOT wait
 *   4. From seed, fork branchB: "add a random move AI opponent" — both
 *      runs now executing concurrently. This is the graph-native move
 *      the demo is here to show: two pending placeholders side-by-side
 *      with spinners, two pi processes working in parallel
 *   5. Wait for both durables to land, then drag-merge them
 *   6. Tour every tab on the merge node
 *   7. Zoom out to show the whole graph
 *
 * Run with: `npx playwright test --config playwright.demo.config.ts`.
 * Wall clock is dominated by the LLM — expect 10–15 min total.
 *
 * Note on ghost-child nodes: every prompt fires a pending placeholder
 * node into the graph immediately so the user sees "ok, the run
 * started" before pi finishes. Pending nodes carry the
 * `.agent-node.pending` CSS class. We filter them out of node-count
 * waits and click targets — the demo is about the durable graph; the
 * pending placeholder is a UX preview the gif captures incidentally
 * but never addresses by selector.
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

	// Hide the side controls panel so the canvas has the whole frame
	// to itself. Layout-mode toggle and Recenter live there but the
	// demo only fires Recenter once via dispatchEvent (works whether
	// the panel is on-screen or transformed off), and waitForNodeCount
	// clicks Refresh the same way. Net effect: more breathing room
	// for the graph in the gif.
	await page.getByRole('button', { name: /^Hide$/ }).dispatchEvent('click');
	await beat(600);

	// 2) The root is now auto-created on `POST /projects/open`, so we
	//    just wait for it to render and click it to open the prompt
	//    popover. The "New root" button only appears in the (now rare)
	//    case where opening the project produced no root.
	// Filter to durable nodes only — pending ghost-children render as
	// `[data-agent-node-id]` too but can't be prompted.
	const durableNodes = page.locator('.agent-node:not(.pending)[data-agent-node-id]');
	await expect(durableNodes.first()).toBeVisible({ timeout: 15_000 });
	await beat(700);
	await durableNodes.first().dispatchEvent('click');
	await beat(500);

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
	// gif viewer can read each one. `:not(.pending)` is defence in
	// depth: by the time waitForNodeCount returns the durable has
	// already replaced the pending in-place, but if the run-completed
	// SSE event lands mid-locator-resolution we don't want to grab a
	// transient ghost-child whose Output tab has nothing to show.
	const seedNode = page
		.locator('.agent-node:not(.pending)[data-agent-node-id][aria-label*="Tic tac toe"]')
		.first();
	// Tab order: end on Changes (the diff) — that's the most concrete
	// "what did the agent actually do" view, and it's where the gif
	// should rest. Events is informational and would land the viewer
	// on a wall of timestamps.
	await tourTabsOn(page, seedNode, ['Output', 'Context', 'Events', 'Changes']);

	// 4–5) Fork two branches off the seed *concurrently*. The orchestrator's
	//      run supervisor accepts a new prompt the moment the API call
	//      returns — the previous run keeps executing in its own task in
	//      the background. Firing branchB before branchA finishes is the
	//      headline graph-native move: two pending placeholders pop in
	//      side-by-side with spinners, both pi processes work in parallel,
	//      and durables land independently. A linear "wait for A, then
	//      send B" demo would hide the entire point.
	//
	// Step 4: re-anchor to the seed and send branchA's prompt. Don't wait
	// for the run to complete — Send returns once the daemon has registered
	// the run and rendered the pending placeholder.
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
	// Brief pause so the gif viewer registers branchA's pending
	// placeholder rendering (spinner kicks in) before we re-anchor.
	await beat(1200);

	// Step 5: re-click the seed to move the popover anchor back from
	// branchA-pending (which was auto-selected on Send) to the seed.
	// Then send branchB's prompt. Now BOTH runs are in flight.
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
	// Hold so the gif viewer sees both pending placeholders side-by-side
	// with their spinners — the parallelism is the visual hook.
	await beat(2000);

	// Wait for BOTH durables to land. expectNodeCount filters out
	// pending placeholders so this is a strict "both real children
	// committed" condition. Then settle so the run-state transitions
	// have propagated downstream (merge classifier reads node.status).
	await waitForNodeCount(page, 4, RUN_TIMEOUT_MS);
	await beat(1500);

	const branchA = page
		.locator('.agent-node:not(.pending)[data-agent-node-id][aria-label*="3-player mode"]')
		.first();
	const branchB = page
		.locator('.agent-node:not(.pending)[data-agent-node-id][aria-label*="Random AI"]')
		.first();

	// Tour both completed branches. Tabs are picked to highlight what
	// the parallel runs actually produced — Output (their event
	// streams), Changes (their independent edits to tictactoe.js).
	await tourTabsOn(page, branchA, ['Output', 'Changes']);
	await tourTabsOn(page, branchB, ['Output', 'Changes']);

	// 6) Recenter, then anchor the popover at root so it sits at the
	//    top of the canvas — clear of the drag targets at the bottom.
	//    (Same trick the resolution e2e test uses.)
	await page.getByRole('button', { name: /^Recenter$/ }).dispatchEvent('click');
	await beat(900);
	await durableNodes.first().dispatchEvent('click');
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

	// 8) Walk through every tab on the merge node, ending on Changes
	//    (the integrated diff). Order: Output → Context → Events →
	//    Artifacts → Merge → Changes. Merge surfaces the conflict
	//    report; Changes is the unified picture and the natural
	//    resting place for a viewer scrubbing the gif.
	const mergeNode = page.locator('.agent-node.kind-merge').first();
	await expect(mergeNode).toBeVisible({ timeout: 15_000 });
	await mergeNode.dispatchEvent('click');
	await beat(700);
	for (const tab of ['Output', 'Context', 'Events', 'Artifacts', 'Merge', 'Changes'] as const) {
		const button = page.getByRole('tab', { name: new RegExp(`^${tab}`) });
		if (await button.count()) {
			await button.first().click();
			await beat(2600);
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
 * Poll for at least `n` *durable* nodes on the canvas, clicking the
 * side-panel "Refresh" button between checks so we don't depend on
 * the SSE event stream alone.
 *
 * Pi runs are long-lived (60–90s of LLM work) and the SSE connection
 * sometimes silently misses the trailing `prompt_node_created` event
 * — refreshing forces a clean `GET /graph`. We also filter pending
 * ghost-children out of the count: those render the moment a prompt
 * is sent (they're a UX preview, not a finished result), so a naive
 * `.agent-node` count would cross the threshold before the LLM
 * actually wrote anything to the worktree, leaving subsequent clicks
 * targeting placeholders we can't prompt or drag-merge.
 */
async function waitForNodeCount(
	page: import('@playwright/test').Page,
	n: number,
	timeoutMs: number
): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	const refresh = page.getByRole('button', { name: /^Refresh$/ });
	while (Date.now() < deadline) {
		const count = await page.locator('.agent-node:not(.pending)').count();
		if (count >= n) return;
		// dispatchEvent so the popover (z-index 25) doesn't eat the click.
		await refresh.first().dispatchEvent('click').catch(() => {});
		await new Promise((r) => setTimeout(r, 2_500));
	}
	const got = await page.locator('.agent-node:not(.pending)').count();
	throw new Error(`waited ${timeoutMs}ms for ${n} durable nodes, got ${got}`);
}

/**
 * Click each tab on the inspector for the given node locator, with a
 * beat between clicks so the gif viewer can register each one. Skips
 * tabs that don't exist (e.g. Merge on a non-merge node).
 *
 * Per-tab dwell is generous (2.6s) so a viewer can actually read each
 * tab — Output's last few lines, the Changes diff hunks, the Context
 * summary. Earlier passes at 1.1s and 1.8s blew past the meaningful
 * content; 2.6s feels right for someone watching the gif at 3x
 * playback speed (PTS/3 in the build script).
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
			await beat(2600);
		}
	}
}
