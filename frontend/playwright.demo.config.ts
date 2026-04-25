/**
 * Playwright config for the demo recording. Mirrors the e2e config —
 * same fixture reset, same daemon + dev-server webServer pair — but:
 *   - records video unconditionally at 1280×720
 *   - targets a different fixture path so it doesn't fight the e2e DB
 *   - runs only tests/demo/* (the test:e2e default excludes tests/demo)
 *   - drives the *real* pi runtime so the gif shows real LLM work
 *
 * Usage:
 *   npx playwright test --config playwright.demo.config.ts
 * The resulting video lands in test-results/<name>/video.webm; the
 * `scripts/build-readme-gif.sh` helper turns it into a sped-up gif.
 *
 * Requires:
 *   - `pi` on PATH and configured (~/.pi/agent/{settings,auth}.json)
 *   - OPENAI_API_KEY available (we read it from orchestrator/.env)
 */

import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';

import { defineConfig, devices } from '@playwright/test';

const FRONTEND_PORT = 5174;
const BACKEND_PORT = 8001;

const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_HEALTH = `http://127.0.0.1:${BACKEND_PORT}/health`;

// Separate fixture from the e2e config so a demo recording can run in
// parallel with normal CI without fighting for state.
const DEMO_REPO = '/tmp/aoc-demo-repo';
const DEMO_DB = '/tmp/aoc-demo.sqlite3';

// Pull OPENAI_API_KEY out of orchestrator/.env so the user doesn't have
// to remember to source it. Falls back to whatever is already in the
// shell environment if the file isn't there.
function loadOpenAIKey(): string {
	const envFromShell = process.env['OPENAI_API_KEY'];
	if (envFromShell) return envFromShell;
	try {
		const contents = readFileSync('../orchestrator/.env', 'utf8');
		for (const line of contents.split(/\r?\n/)) {
			const match = /^OPENAI_API_KEY=(.*)$/.exec(line.trim());
			if (match) return match[1];
		}
	} catch {
		// ignore — fall through to empty
	}
	return '';
}

const OPENAI_API_KEY = loadOpenAIKey();

const IS_WORKER =
	process.env['TEST_WORKER_INDEX'] !== undefined ||
	process.env['PW_TEST_WORKER_INDEX'] !== undefined;
if (!IS_WORKER) {
	resetFixture();
}

function resetFixture() {
	for (const suffix of ['', '-journal', '-wal', '-shm']) {
		const p = `${DEMO_DB}${suffix}`;
		if (existsSync(p)) rmSync(p);
	}
	if (existsSync(DEMO_REPO)) rmSync(DEMO_REPO, { recursive: true, force: true });
	mkdirSync(DEMO_REPO, { recursive: true });
	writeFileSync(`${DEMO_REPO}/README.md`, '# demo fixture\n');
	const env = {
		...process.env,
		GIT_AUTHOR_NAME: 'demo',
		GIT_AUTHOR_EMAIL: 'demo@aoc.local',
		GIT_COMMITTER_NAME: 'demo',
		GIT_COMMITTER_EMAIL: 'demo@aoc.local'
	};
	const sh = (cmd: string) => execSync(cmd, { cwd: DEMO_REPO, env, stdio: 'pipe' });
	sh('git init -q -b main');
	sh('git add README.md');
	sh('git commit -q -m init');
}

export default defineConfig({
	testDir: './tests/demo',
	// Real pi runs are slow — three prompts + a merge can take 10+ min
	// of wall clock. Give the suite plenty of room.
	timeout: 1_800_000,
	fullyParallel: false,
	workers: 1,
	retries: 0,
	reporter: [['list']],
	use: {
		baseURL: FRONTEND_URL,
		trace: 'off',
		screenshot: 'off',
		video: {
			mode: 'on',
			size: { width: 1280, height: 720 }
		},
		viewport: { width: 1280, height: 720 }
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
	webServer: [
		{
			command: `cd ../orchestrator && AOC_HOST=127.0.0.1 AOC_PORT=${BACKEND_PORT} AOC_RUNTIME_BACKEND=pi AOC_DATABASE_URL=sqlite+aiosqlite:///${DEMO_DB} .venv/bin/python -m agentsofchaos_orchestrator.main`,
			url: BACKEND_HEALTH,
			reuseExistingServer: false,
			stdout: 'pipe',
			stderr: 'pipe',
			timeout: 60_000,
			env: { ...process.env, PYTHONUNBUFFERED: '1', OPENAI_API_KEY }
		},
		{
			// Point the dev-server proxy at the demo backend port so
			// /api/orchestrator/* resolves to the right daemon.
			command: `ORCHESTRATOR_BASE_URL=http://127.0.0.1:${BACKEND_PORT} npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
			url: FRONTEND_URL,
			reuseExistingServer: false,
			stdout: 'pipe',
			stderr: 'pipe',
			timeout: 60_000
		}
	]
});
