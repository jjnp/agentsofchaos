const http = require('http');
const fs = require('fs');
const path = require('path');
const { randomUUID } = require('crypto');
const Docker = require('dockerode');
const OpenAI = require('openai');
const WebSocket = require('ws');
const { WebSocketServer } = require('ws');
const tar = require('tar-stream');

const PORT = Number(process.env.PORT || 3000);
const PI_MODEL = process.env.PI_MODEL || 'openai/gpt-4o-mini';
const MERGE_MODEL = process.env.MERGE_MODEL || 'gpt-4o-mini';
const WORKER_IMAGE = process.env.WORKER_IMAGE || 'agentsofchaos/pi-worker:latest';
const WORKER_NETWORK = process.env.WORKER_NETWORK || 'agentsofchaos-grid';
const WORKER_INTERNAL_PORT = Number(process.env.WORKER_INTERNAL_PORT || 3000);
const GRID_SIZE = Number(process.env.GRID_SIZE || 4);
const docker = new Docker({ socketPath: '/var/run/docker.sock' });
const openai = process.env.OPENAI_API_KEY ? new OpenAI({ apiKey: process.env.OPENAI_API_KEY }) : null;

function sendJson(ws, payload) {
  if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function shellEscape(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function clipText(text, maxChars = 24000) {
  if (!text) return '';
  if (text.length <= maxChars) return text;
  const head = text.slice(0, Math.floor(maxChars * 0.6));
  const tail = text.slice(-Math.floor(maxChars * 0.4));
  return `${head}\n\n...[truncated ${text.length - maxChars} chars]...\n\n${tail}`;
}

function createTarBuffer(fileName, content) {
  return new Promise((resolve, reject) => {
    const pack = tar.pack();
    const chunks = [];

    pack.on('data', (chunk) => chunks.push(chunk));
    pack.on('end', () => resolve(Buffer.concat(chunks)));
    pack.on('error', reject);

    pack.entry({ name: fileName, mode: 0o600 }, content, (error) => {
      if (error) return reject(error);
      pack.finalize();
    });
  });
}

async function ensureNetwork() {
  const networks = await docker.listNetworks({ filters: { name: [WORKER_NETWORK] } });
  if (networks.some((network) => network.Name === WORKER_NETWORK)) return;
  await docker.createNetwork({ Name: WORKER_NETWORK, CheckDuplicate: true });
}

async function summarizeMergedContext({ source, target, mergeResult }) {
  if (!openai) {
    return [
      '# Merge Context',
      '',
      `Model summary unavailable because OPENAI_API_KEY is not set in the orchestrator.`,
      '',
      `## Source (${source.label})`,
      source.session?.content ? clipText(source.session.content, 4000) : 'No persisted pi session found.',
      '',
      `## Target (${target.label})`,
      target.session?.content ? clipText(target.session.content, 4000) : 'No persisted pi session found.',
      '',
      `## Git merge output`,
      '```',
      clipText(`${mergeResult.stdout}\n${mergeResult.stderr}`, 4000),
      '```',
    ].join('\n');
  }

  const prompt = [
    'You are preparing merged context for a coding agent after two branches were merged.',
    'Produce concise markdown with these sections exactly:',
    '1. # Merge Context',
    '2. ## Source Branch Summary',
    '3. ## Target Branch Summary',
    '4. ## Combined Intent',
    '5. ## Important Files or Risks',
    '6. ## Suggested Next Prompt',
    '',
    'Use the git merge output and the two pi session logs below.',
    'If a session is missing, say so briefly.',
    'Keep it under 700 words.',
    '',
    `Source label: ${source.label}`,
    `Source latest session path: ${source.session?.path || 'none'}`,
    '```jsonl',
    clipText(source.session?.content || 'No persisted pi session found.'),
    '```',
    '',
    `Target label: ${target.label}`,
    `Target latest session path: ${target.session?.path || 'none'}`,
    '```jsonl',
    clipText(target.session?.content || 'No persisted pi session found.'),
    '```',
    '',
    'Git merge output:',
    '```text',
    clipText(`${mergeResult.stdout}\n${mergeResult.stderr}`, 12000),
    '```',
  ].join('\n');

  const response = await openai.responses.create({
    model: MERGE_MODEL,
    input: prompt,
  });

  return response.output_text || '# Merge Context\n\nNo summary returned.';
}

class WorkerHandle {
  constructor(session, slot, sourceImage) {
    this.session = session;
    this.slot = slot;
    this.sourceImage = sourceImage;
    this.containerName = `aoc-${session.id}-slot-${slot + 1}`;
    this.label = `pi-${slot + 1}`;
    this.container = null;
    this.ws = null;
    this.sessionId = null;
  }

  emit(payload) {
    this.session.emit({ slot: this.slot, label: this.label, ...payload });
  }

  async start() {
    await ensureNetwork();
    const container = await docker.createContainer({
      Image: this.sourceImage,
      name: this.containerName,
      Env: [
        `OPENAI_API_KEY=${process.env.OPENAI_API_KEY || ''}`,
        `PI_MODEL=${PI_MODEL}`,
        `INSTANCE_LABEL=${this.label}`,
        `PORT=${WORKER_INTERNAL_PORT}`,
        'PI_WORKSPACE=/workspace',
        'PI_CODING_AGENT_DIR=/state/pi-agent',
      ],
      ExposedPorts: { [`${WORKER_INTERNAL_PORT}/tcp`]: {} },
      HostConfig: {
        AutoRemove: true,
        NetworkMode: WORKER_NETWORK,
        Memory: 2147483648,
        NanoCpus: 2_000_000_000,
      },
      Labels: {
        'agentsofchaos.session': this.session.id,
        'agentsofchaos.slot': String(this.slot),
        'agentsofchaos.role': 'worker',
      },
    });

    this.container = container;
    await container.start();
    this.emit({ type: 'worker_container_started', containerName: this.containerName, image: this.sourceImage });
    await this.connectWebSocket();
  }

  async connectWebSocket() {
    let lastError = null;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      try {
        await new Promise((resolve, reject) => {
          const ws = new WebSocket(`ws://${this.containerName}:${WORKER_INTERNAL_PORT}`);
          const timeout = setTimeout(() => {
            ws.terminate();
            reject(new Error('Timed out connecting to worker websocket'));
          }, 2000);

          ws.once('open', () => {
            clearTimeout(timeout);
            this.ws = ws;
            ws.on('message', (buffer) => {
              const payload = JSON.parse(buffer.toString('utf8'));
              if (payload.type === 'session_ready') this.sessionId = payload.sessionId;
              this.emit(payload);
            });
            ws.on('close', () => {
              this.emit({ type: 'worker_socket_closed' });
            });
            resolve();
          });

          ws.once('error', (error) => {
            clearTimeout(timeout);
            reject(error);
          });
        });

        return;
      } catch (error) {
        lastError = error;
        await delay(500);
      }
    }

    throw lastError || new Error('Unable to connect to worker websocket');
  }

  send(payload) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error(`Worker ${this.label} is not connected`);
    }
    this.ws.send(JSON.stringify(payload));
  }

  async exec(command, options = {}) {
    if (!this.container) throw new Error(`Worker ${this.label} has no running container`);

    const exec = await this.container.exec({
      AttachStdout: true,
      AttachStderr: true,
      AttachStdin: Boolean(options.stdin),
      Tty: false,
      WorkingDir: options.cwd,
      Cmd: ['sh', '-lc', command],
    });

    const stream = await exec.start({ hijack: true, stdin: Boolean(options.stdin) });
    const stdoutChunks = [];
    const stderrChunks = [];

    await new Promise((resolve, reject) => {
      this.container.modem.demuxStream(stream, {
        write: (chunk) => stdoutChunks.push(Buffer.from(chunk)),
      }, {
        write: (chunk) => stderrChunks.push(Buffer.from(chunk)),
      });

      stream.on('error', reject);
      stream.on('end', resolve);

      if (options.stdin) {
        stream.write(options.stdin);
      }
      stream.end();
    });

    const inspect = await exec.inspect();
    return {
      exitCode: inspect.ExitCode ?? 0,
      stdout: Buffer.concat(stdoutChunks).toString('utf8'),
      stderr: Buffer.concat(stderrChunks).toString('utf8'),
    };
  }

  async putFile(targetPath, content) {
    if (!this.container) throw new Error(`Worker ${this.label} has no running container`);
    const dir = path.posix.dirname(targetPath);
    const fileName = path.posix.basename(targetPath);
    const archive = await createTarBuffer(fileName, content);
    await this.container.putArchive(archive, { path: dir });
  }

  async readFile(filePath) {
    const archive = await this.container.getArchive({ path: filePath });
    const chunks = [];
    await new Promise((resolve, reject) => {
      archive.on('data', (chunk) => chunks.push(chunk));
      archive.on('end', resolve);
      archive.on('error', reject);
    });

    return await new Promise((resolve, reject) => {
      const extract = tar.extract();
      let content = Buffer.alloc(0);

      extract.on('entry', (_header, stream, next) => {
        const fileChunks = [];
        stream.on('data', (chunk) => fileChunks.push(chunk));
        stream.on('end', () => {
          content = Buffer.concat(fileChunks);
          next();
        });
        stream.on('error', reject);
      });

      extract.on('finish', () => resolve(content));
      extract.on('error', reject);
      extract.end(Buffer.concat(chunks));
    });
  }

  async ensureGitRepo() {
    const result = await this.exec('git -C /workspace rev-parse --is-inside-work-tree');
    if (result.exitCode !== 0) {
      throw new Error(`Worker ${this.label} does not have a git repo in /workspace`);
    }
  }

  async checkpointIfDirty(reason) {
    await this.ensureGitRepo();
    const result = await this.exec([
      'git -C /workspace add -A',
      `if git -C /workspace diff --cached --quiet; then echo clean; else git -C /workspace commit -m ${shellEscape(`agent checkpoint: ${reason}`)} >/dev/null && echo committed; fi`,
    ].join(' && '));

    if (result.exitCode !== 0) {
      throw new Error(`Checkpoint failed for ${this.label}: ${result.stderr || result.stdout}`);
    }

    const state = result.stdout.trim().split(/\s+/).pop() || 'unknown';
    this.emit({ type: 'checkpoint_created', reason, state });
    return state;
  }

  async exportBundle() {
    await this.checkpointIfDirty(`bundle export ${this.label}`);
    const bundlePath = `/tmp/${this.session.id}-${this.slot + 1}.bundle`;
    const result = await this.exec(`git -C /workspace bundle create ${shellEscape(bundlePath)} --all`);
    if (result.exitCode !== 0) {
      throw new Error(`Bundle export failed for ${this.label}: ${result.stderr || result.stdout}`);
    }
    const bundle = await this.readFile(bundlePath);
    this.emit({ type: 'bundle_exported', bytes: bundle.length, path: bundlePath });
    return bundle;
  }

  async importBundle(bundle, remoteName) {
    await this.ensureGitRepo();
    const bundlePath = `/tmp/${remoteName}.bundle`;
    await this.putFile(bundlePath, bundle);
    const result = await this.exec([
      `git -C /workspace remote remove ${shellEscape(remoteName)} >/dev/null 2>&1 || true`,
      `git -C /workspace remote add ${shellEscape(remoteName)} ${shellEscape(bundlePath)}`,
      `git -C /workspace fetch ${shellEscape(remoteName)}`,
    ].join(' && '));

    if (result.exitCode !== 0) {
      throw new Error(`Bundle import failed for ${this.label}: ${result.stderr || result.stdout}`);
    }

    this.emit({ type: 'bundle_imported', bytes: bundle.length, remoteName, path: bundlePath });
    return { remoteName, path: bundlePath };
  }

  async mergeFetchedRemote(remoteName, branch = 'main') {
    await this.checkpointIfDirty(`pre-merge ${this.label}`);
    const mergeTarget = `${remoteName}/${branch}`;
    const result = await this.exec(`git -C /workspace merge --no-edit --no-ff ${shellEscape(mergeTarget)}`);
    this.emit({
      type: result.exitCode === 0 ? 'git_merge_succeeded' : 'git_merge_conflicted',
      remoteName,
      branch,
      exitCode: result.exitCode,
      output: `${result.stdout}${result.stderr}`.trim(),
    });
    return result;
  }

  async inspectGitStatus() {
    await this.ensureGitRepo();
    const result = await this.exec('git -C /workspace status --short --branch');
    if (result.exitCode !== 0) {
      throw new Error(`git status failed for ${this.label}: ${result.stderr || result.stdout}`);
    }
    this.emit({ type: 'git_status', status: result.stdout.trim() });
    return result.stdout.trim();
  }

  async getLatestSession() {
    const locate = await this.exec("latest=$(find /state/pi-agent/sessions -type f -name '*.jsonl' 2>/dev/null | sort | tail -n 1); if [ -n \"$latest\" ]; then printf '%s' \"$latest\"; fi");
    if (locate.exitCode !== 0) {
      throw new Error(`Failed to locate session for ${this.label}: ${locate.stderr || locate.stdout}`);
    }

    const latestPath = locate.stdout.trim();
    if (!latestPath) return null;
    const content = (await this.readFile(latestPath)).toString('utf8');
    return { path: latestPath, content };
  }

  async writeMergeContext(markdown, details) {
    await this.putFile('/state/meta/merge-context.md', markdown);
    await this.putFile('/state/meta/merge-details.json', JSON.stringify(details, null, 2));
    this.emit({ type: 'merge_context_written', path: '/state/meta/merge-context.md' });
  }

  async commitSnapshot() {
    if (!this.container) throw new Error(`Worker ${this.label} has no running container`);
    const tag = `${this.session.id}-slot-${this.slot + 1}-${Date.now()}`.toLowerCase();
    const repo = 'agentsofchaos/pi-snapshot';
    await this.container.commit({ repo, tag, pause: true });
    const image = `${repo}:${tag}`;
    this.session.snapshotImages.add(image);
    this.emit({ type: 'fork_snapshot_created', image });
    return image;
  }

  async replaceFromImage(image) {
    await this.stop();
    this.sourceImage = image;
    await this.start();
  }

  async stop() {
    if (this.ws) {
      try { this.ws.close(); } catch {}
      this.ws = null;
    }

    if (!this.container) return;

    try {
      await this.container.stop({ t: 1 });
    } catch {}

    try {
      await this.container.remove({ force: true });
    } catch {}

    this.container = null;
  }
}

class BrowserSession {
  constructor(ws) {
    this.ws = ws;
    this.id = randomUUID().replace(/-/g, '').slice(0, 12);
    this.workers = [];
    this.snapshotImages = new Set();
  }

  emit(payload) {
    sendJson(this.ws, payload);
  }

  async initialize() {
    this.emit({ type: 'grid_boot', session: this.id, gridSize: GRID_SIZE, model: PI_MODEL, mergeModel: MERGE_MODEL });
    for (let slot = 0; slot < GRID_SIZE; slot += 1) {
      const worker = new WorkerHandle(this, slot, WORKER_IMAGE);
      this.workers.push(worker);
      await worker.start();
      await worker.inspectGitStatus().catch((error) => worker.emit({ type: 'git_status_error', message: error.message }));
    }
    this.emit({ type: 'grid_ready', session: this.id, gridSize: GRID_SIZE, model: PI_MODEL });
  }

  getWorker(slot) {
    if (!Number.isInteger(slot) || slot < 0 || slot >= this.workers.length) {
      throw new Error(`Invalid slot: ${slot}`);
    }
    return this.workers[slot];
  }

  prompt(slot, message) {
    this.getWorker(slot).send({ type: 'prompt', message });
  }

  promptAll(message) {
    this.workers.forEach((worker) => worker.send({ type: 'prompt', message }));
  }

  abort(slot) {
    this.getWorker(slot).send({ type: 'abort' });
  }

  abortAll() {
    this.workers.forEach((worker) => worker.send({ type: 'abort' }));
  }

  async fork(sourceSlot, targetSlot) {
    if (sourceSlot === targetSlot) throw new Error('Source and target slots must differ');
    const source = this.getWorker(sourceSlot);
    const target = this.getWorker(targetSlot);
    this.emit({ type: 'fork_start', sourceSlot, targetSlot, sourceLabel: source.label, targetLabel: target.label });
    const image = await source.commitSnapshot();
    await target.replaceFromImage(image);
    await target.inspectGitStatus().catch((error) => target.emit({ type: 'git_status_error', message: error.message }));
    this.emit({ type: 'fork_complete', sourceSlot, targetSlot, image });
  }

  async prepareMergeBundle(sourceSlot, targetSlot) {
    if (sourceSlot === targetSlot) throw new Error('Source and target slots must differ');
    const source = this.getWorker(sourceSlot);
    const target = this.getWorker(targetSlot);
    const remoteName = `merge_slot_${sourceSlot + 1}`;

    this.emit({ type: 'merge_prep_start', sourceSlot, targetSlot, remoteName });
    const bundle = await source.exportBundle();
    const imported = await target.importBundle(bundle, remoteName);
    await target.inspectGitStatus().catch((error) => target.emit({ type: 'git_status_error', message: error.message }));
    this.emit({
      type: 'merge_prep_complete',
      sourceSlot,
      targetSlot,
      remoteName: imported.remoteName,
      bytes: bundle.length,
      nextStep: `git -C /workspace merge ${remoteName}/main || git -C /workspace log --oneline --all --graph`,
    });
  }

  async merge(sourceSlot, targetSlot) {
    if (sourceSlot === targetSlot) throw new Error('Source and target slots must differ');
    const source = this.getWorker(sourceSlot);
    const target = this.getWorker(targetSlot);
    const remoteName = `merge_slot_${sourceSlot + 1}`;

    this.emit({ type: 'merge_start', sourceSlot, targetSlot, sourceLabel: source.label, targetLabel: target.label });
    const bundle = await source.exportBundle();
    await target.importBundle(bundle, remoteName);
    const mergeResult = await target.mergeFetchedRemote(remoteName, 'main');
    const [sourceSession, targetSession] = await Promise.all([
      source.getLatestSession().catch(() => null),
      target.getLatestSession().catch(() => null),
    ]);

    const mergeContext = await summarizeMergedContext({
      source: { label: source.label, session: sourceSession },
      target: { label: target.label, session: targetSession },
      mergeResult,
    });

    await target.writeMergeContext(mergeContext, {
      sourceSlot,
      targetSlot,
      remoteName,
      mergeExitCode: mergeResult.exitCode,
      sourceSessionPath: sourceSession?.path || null,
      targetSessionPath: targetSession?.path || null,
      mergeStdout: mergeResult.stdout,
      mergeStderr: mergeResult.stderr,
    });

    await target.inspectGitStatus().catch((error) => target.emit({ type: 'git_status_error', message: error.message }));
    this.emit({
      type: 'merge_complete',
      sourceSlot,
      targetSlot,
      remoteName,
      mergeExitCode: mergeResult.exitCode,
      mergeContextPath: '/state/meta/merge-context.md',
    });
  }

  async dispose() {
    await Promise.all(this.workers.map((worker) => worker.stop().catch(() => {})));
    await Promise.all([...this.snapshotImages].map(async (image) => {
      try {
        await docker.getImage(image).remove({ force: true });
      } catch {}
    }));
  }
}

const publicDir = path.join(__dirname, 'public');
const server = http.createServer((req, res) => {
  const reqPath = req.url === '/' ? '/index.html' : req.url;
  const filePath = path.join(publicDir, path.normalize(reqPath));

  if (!filePath.startsWith(publicDir)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, content) => {
    if (err) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }

    const ext = path.extname(filePath);
    const type = ext === '.html'
      ? 'text/html; charset=utf-8'
      : ext === '.js'
        ? 'application/javascript; charset=utf-8'
        : ext === '.css'
          ? 'text/css; charset=utf-8'
          : 'text/plain; charset=utf-8';

    res.writeHead(200, { 'Content-Type': type });
    res.end(content);
  });
});

const wss = new WebSocketServer({ server });

wss.on('connection', async (ws) => {
  const session = new BrowserSession(ws);

  try {
    await session.initialize();
  } catch (error) {
    sendJson(ws, { type: 'bridge_error', message: error.message });
    await session.dispose();
    ws.close();
    return;
  }

  ws.on('message', async (buffer) => {
    try {
      const message = JSON.parse(buffer.toString('utf8'));
      if (message.type === 'prompt') return session.prompt(message.target, message.message);
      if (message.type === 'prompt_all') return session.promptAll(message.message);
      if (message.type === 'abort') return session.abort(message.target);
      if (message.type === 'abort_all') return session.abortAll();
      if (message.type === 'fork') return await session.fork(message.source, message.target);
      if (message.type === 'prepare_merge') return await session.prepareMergeBundle(message.source, message.target);
      if (message.type === 'merge') return await session.merge(message.source, message.target);
      sendJson(ws, { type: 'bridge_error', message: 'Unsupported client message' });
    } catch (error) {
      sendJson(ws, { type: 'bridge_error', message: error.message });
    }
  });

  ws.on('close', async () => {
    await session.dispose();
  });
});

server.listen(PORT, () => {
  console.log(`orchestrator listening on http://0.0.0.0:${PORT}`);
});
