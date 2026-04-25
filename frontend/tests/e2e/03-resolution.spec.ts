import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';

import {
	clickTab,
	createRoot,
	dragMergeLocators,
	expectNodeCount,
	openProject,
	selectNode,
	sendPrompt
} from './helpers';

// Self-contained fixture so this spec doesn't fight the daemon state
// 01-smoke and 02-interaction leave behind. The orchestrator supports
// many open projects on the same daemon — we just open a second one.
const RESOLUTION_REPO = '/tmp/aoc-e2e-resolution-repo';

function ensureFreshRepo(path: string) {
	if (existsSync(path)) rmSync(path, { recursive: true, force: true });
	mkdirSync(path, { recursive: true });
	writeFileSync(`${path}/README.md`, '# resolution e2e fixture\n');
	const env = {
		...process.env,
		GIT_AUTHOR_NAME: 'e2e',
		GIT_AUTHOR_EMAIL: 'e2e@agentsofchaos.local',
		GIT_COMMITTER_NAME: 'e2e',
		GIT_COMMITTER_EMAIL: 'e2e@agentsofchaos.local'
	};
	execSync('git init -q -b main', { cwd: path, env, stdio: 'pipe' });
	execSync('git add README.md', { cwd: path, env, stdio: 'pipe' });
	execSync('git commit -q -m init', { cwd: path, env, stdio: 'pipe' });
}

test.describe.serial('resolution', () => {
	test.beforeAll(() => {
		ensureFreshRepo(RESOLUTION_REPO);
	});

	test('drives a code-conflicted merge through the Resolve form', async ({ page }) => {
		test.setTimeout(60_000);

		// Surface the merge POST in test logs so a regression in the
		// drag-to-merge gesture is easy to spot.
		page.on('request', (req) => {
			const url = req.url();
			if (url.includes('/merges') || url.includes('/resolution-runs')) {
				console.log(`[net] ${req.method()} ${url}`);
			}
		});
		page.on('response', async (resp) => {
			const url = resp.url();
			if (url.includes('/merges') || url.includes('/resolution-runs')) {
				console.log(`[net] ${resp.status()} ${url}`);
			}
		});

		await openProject(page, RESOLUTION_REPO);
		await createRoot(page);

		// 1) Seed a file at the root → both branches inherit it as the
		//    common ancestor for the merge classifier. The noop runtime
		//    writes <name>:<content> prompts to the worktree (only when
		//    the prompt matches the bare-filename pattern).
		await sendPrompt(page, 'conflict.txt:original');
		await expectNodeCount(page, 2, 30_000);

		// 2) Two divergent siblings off the SEED node so the merge has
		//    a real ancestor != either side. Re-anchor by clicking the
		//    seed (the second node — index 1 because root is 0).
		await selectNode(page, 1);
		await sendPrompt(page, 'conflict.txt:source-version');
		await expectNodeCount(page, 3, 30_000);

		await selectNode(page, 1);
		await sendPrompt(page, 'conflict.txt:target-version');
		await expectNodeCount(page, 4, 30_000);

		// 3) Drag-merge the two siblings. Locate by aria-label so we
		//    don't depend on the canvas's traversal order. Recenter
		//    first — adding nodes pushes the layout out and the canvas
		//    doesn't auto-frame to fit; without this the source/target
		//    nodes can sit off-screen and dragMerge picks empty space.
		// dispatchEvent bypasses the pointer-events hit test — the
		// popover (z-index 25) sits over the side controls panel.
		await page
			.getByRole('button', { name: /^Recenter$/ })
			.dispatchEvent('click');
		await selectNode(page, 0);
		const sourceNode = page.locator(
			'[data-agent-node-id][aria-label*="conflict.txt:source-version"]'
		);
		const targetNode = page.locator(
			'[data-agent-node-id][aria-label*="conflict.txt:target-version"]'
		);
		await expect(sourceNode).toBeInViewport({ timeout: 5_000 });
		await expect(targetNode).toBeInViewport({ timeout: 5_000 });
		await dragMergeLocators(page, sourceNode, targetNode);
		await expectNodeCount(page, 5, 30_000);

		const mergeNode = page.locator('.agent-node.kind-merge').first();
		await expect(mergeNode).toBeVisible({ timeout: 15_000 });
		// Conflict produces a non-`ready` status. The exact status depends
		// on whether context conflicts also fired — for code-only fixture
		// prompts it's code_conflicted.
		await expect
			.poll(() => mergeNode.getAttribute('class').then((c) => c ?? ''))
			.toMatch(/status-(code-conflicted|both-conflicted)/);

		// 4) Open the Merge tab and verify the Resolve form rendered.
		await mergeNode.dispatchEvent('click');
		await clickTab(page, 'Merge');
		const resolveForm = page.locator('.merge-report .resolve-form');
		await expect(resolveForm).toBeVisible({ timeout: 15_000 });

		// 5) Submit a resolution. The noop fixture-mode runtime writes
		//    conflict.txt with "resolved" content (no markers), so the
		//    backend's conflict-marker validation passes and the
		//    successor RESOLUTION node materialises.
		await resolveForm
			.locator('textarea')
			.fill('conflict.txt:resolved-version');
		await resolveForm.getByRole('button', { name: /^Resolve$/ }).click();

		// A new RESOLUTION node appears (count = 6) and is rendered with
		// the kind-resolution class.
		await expectNodeCount(page, 6, 30_000);
		const resolutionNode = page.locator('.agent-node.kind-resolution').first();
		await expect(resolutionNode).toBeVisible({ timeout: 15_000 });

		// Artifacts tab on the merge node lists the merge report. The
		// resolution backend writes the resolution report against the
		// successor node — exercise that path too.
		await mergeNode.dispatchEvent('click');
		await clickTab(page, 'Artifacts');
		await expect(
			page.locator('.artifacts .row .kind').filter({ hasText: 'merge_report' })
		).toBeVisible({ timeout: 15_000 });

		await resolutionNode.dispatchEvent('click');
		await clickTab(page, 'Artifacts');
		await expect(
			page.locator('.artifacts .row .kind').filter({ hasText: 'resolution_report' })
		).toBeVisible({ timeout: 15_000 });
	});
});
