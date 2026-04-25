import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';

import { defineConfig, devices } from '@playwright/test';

const FRONTEND_PORT = 5173;
const BACKEND_PORT = 8000;

const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_HEALTH = `http://127.0.0.1:${BACKEND_PORT}/health`;

// Fresh per `npm run test:e2e` invocation — done at config-load time so the
// daemon (started by webServer below) sees a clean repo + empty DB before it
// initialises the SQLAlchemy schema. Doing this in globalSetup races against
// webServer startup and ends with "no such table: projects".
const E2E_REPO = '/tmp/aoc-e2e-repo';
const E2E_DB = '/tmp/aoc-e2e.sqlite3';

// Print diagnostic so we can see which Playwright process loaded this config.
console.log(
	`[playwright.config] pid=${process.pid} TEST_WORKER_INDEX=${process.env['TEST_WORKER_INDEX'] ?? 'unset'} PW_TEST_WORKER_INDEX=${process.env['PW_TEST_WORKER_INDEX'] ?? 'unset'}`
);

// Run only on the main process. Worker processes also load this config and
// must NOT wipe state out from under the daemon.
const IS_WORKER =
	process.env['TEST_WORKER_INDEX'] !== undefined ||
	process.env['PW_TEST_WORKER_INDEX'] !== undefined;
if (!IS_WORKER) {
	resetFixture();
}

function resetFixture() {
	for (const suffix of ['', '-journal', '-wal', '-shm']) {
		const p = `${E2E_DB}${suffix}`;
		if (existsSync(p)) rmSync(p);
	}
	if (existsSync(E2E_REPO)) rmSync(E2E_REPO, { recursive: true, force: true });
	mkdirSync(E2E_REPO, { recursive: true });
	writeFileSync(`${E2E_REPO}/README.md`, '# e2e fixture\n');
	const env = {
		...process.env,
		GIT_AUTHOR_NAME: 'e2e',
		GIT_AUTHOR_EMAIL: 'e2e@agentsofchaos.local',
		GIT_COMMITTER_NAME: 'e2e',
		GIT_COMMITTER_EMAIL: 'e2e@agentsofchaos.local'
	};
	const sh = (cmd: string) => execSync(cmd, { cwd: E2E_REPO, env, stdio: 'pipe' });
	sh('git init -q -b main');
	sh('git add README.md');
	sh('git commit -q -m init');
	console.log(`[e2e] fresh fixture at ${E2E_REPO}, sqlite cleared at ${E2E_DB}`);
}

export default defineConfig({
	testDir: './tests/e2e',
	timeout: 60_000,
	expect: { timeout: 10_000 },
	fullyParallel: false,
	workers: 1,
	// No retries: daemon state persists across attempts, so a retry sees a
	// graph with extra nodes and assertions like toHaveCount(1) start failing.
	retries: 0,
	reporter: [['list'], ['html', { open: 'never' }]],
	use: {
		baseURL: FRONTEND_URL,
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
		video: 'retain-on-failure'
	},
	projects: [
		{
			name: 'chromium',
			use: { ...devices['Desktop Chrome'] }
		}
	],
	webServer: [
		{
			// Backend daemon: noop runtime so tests don't hit OpenAI; isolated sqlite.
			// Logged to /tmp/aoc-e2e-daemon.log for post-mortem debugging.
			command: `bash -c 'cd ../orchestrator && AOC_HOST=127.0.0.1 AOC_RUNTIME_BACKEND=noop AOC_DATABASE_URL="sqlite+aiosqlite:///${E2E_DB}" .venv/bin/python -m agentsofchaos_orchestrator.main 2>&1 | tee /tmp/aoc-e2e-daemon.log'`,
			url: BACKEND_HEALTH,
			reuseExistingServer: !process.env['CI'],
			stdout: 'pipe',
			stderr: 'pipe',
			timeout: 60_000
		},
		{
			command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
			url: FRONTEND_URL,
			reuseExistingServer: !process.env['CI'],
			stdout: 'pipe',
			stderr: 'pipe',
			timeout: 60_000
		}
	]
});
