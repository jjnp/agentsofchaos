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

function sendJsonResponse(res, statusCode, payload) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

function sendTextResponse(res, statusCode, text, contentType = 'text/plain; charset=utf-8') {
  res.writeHead(statusCode, { 'Content-Type': contentType });
  res.end(text);
}

async function readJsonBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString('utf8').trim();
  if (!raw) return {};
  return JSON.parse(raw);
}

function sendApiError(res, statusCode, code, message) {
  sendJsonResponse(res, statusCode, { error: { code, message } });
}

function startSse(res) {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
  });
  res.write(': connected\n\n');
}

function writeSseEvent(res, payload, eventId = null) {
  if (eventId != null) res.write(`id: ${eventId}\n`);
  res.write('event: message\n');
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
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

function safeJsonlParse(content) {
  return String(content || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

function summarizeSessionUsage(entries) {
  const assistants = entries.filter((entry) => entry.role === 'assistant');
  const latestAssistant = assistants.at(-1) || null;
  const totals = assistants.reduce((acc, entry) => {
    const usage = entry.usage || {};
    acc.inputTokens += usage.input || 0;
    acc.outputTokens += usage.output || 0;
    acc.cacheReadTokens += usage.cacheRead || 0;
    acc.cacheWriteTokens += usage.cacheWrite || 0;
    acc.totalTokens += usage.totalTokens || 0;
    return acc;
  }, {
    assistantMessages: assistants.length,
    totalEntries: entries.length,
    inputTokens: 0,
    outputTokens: 0,
    cacheReadTokens: 0,
    cacheWriteTokens: 0,
    totalTokens: 0,
  });

  return {
    ...totals,
    latestResponseTokens: latestAssistant?.usage?.totalTokens || 0,
    latestStopReason: latestAssistant?.stopReason || null,
  };
}

function shortSha(value) {
  return value ? String(value).slice(0, 12) : null;
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
    this.label = `pi-${slot + 1}`;
    this.agentUuid = `piagent_${randomUUID().replace(/-/g, '').slice(0, 16)}`;
    this.containerName = '';
    this.container = null;
    this.ws = null;
    this.sessionId = null;
    this.lastGitStatus = null;
    this.lastForkPoint = null;
  }

  emit(payload) {
    this.session.emit({ slot: this.slot, label: this.label, ...payload });
  }

  async start() {
    await ensureNetwork();
    this.containerName = `aoc-${this.agentUuid}`;
    const container = await docker.createContainer({
      Image: this.sourceImage,
      name: this.containerName,
      Env: [
        `OPENAI_API_KEY=${process.env.OPENAI_API_KEY || ''}`,
        `PI_MODEL=${PI_MODEL}`,
        `INSTANCE_LABEL=${this.label}`,
        `PI_AGENT_UUID=${this.agentUuid}`,
        `PORT=${WORKER_INTERNAL_PORT}`,
        'PI_WORKSPACE=/workspace',
        'PI_CODING_AGENT_DIR=/state/pi-agent',
      ],
      ExposedPorts: { [`${WORKER_INTERNAL_PORT}/tcp`]: {} },
      HostConfig: {
        NetworkMode: WORKER_NETWORK,
        Memory: 2147483648,
        NanoCpus: 2_000_000_000,
      },
      Labels: {
        'agentsofchaos.session': this.session.id,
        'agentsofchaos.slot': String(this.slot),
        'agentsofchaos.role': 'worker',
        'agentsofchaos.agent_uuid': this.agentUuid,
      },
    });

    this.container = container;
    await container.start();
    this.emit({ type: 'worker_container_started', containerName: this.containerName, image: this.sourceImage, agentUuid: this.agentUuid });
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
              this.emit({ agentUuid: this.agentUuid, containerName: this.containerName, ...payload });
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

  async writeJson(targetPath, value) {
    await this.putFile(targetPath, JSON.stringify(value, null, 2));
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

  async readTextFile(filePath) {
    return (await this.readFile(filePath)).toString('utf8');
  }

  async readJsonFile(filePath) {
    return JSON.parse(await this.readTextFile(filePath));
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
    this.lastGitStatus = result.stdout.trim();
    this.emit({ type: 'git_status', status: this.lastGitStatus });
    return this.lastGitStatus;
  }

  async getGitHead() {
    await this.ensureGitRepo();
    const result = await this.exec('git -C /workspace rev-parse HEAD');
    if (result.exitCode !== 0) {
      throw new Error(`git rev-parse failed for ${this.label}: ${result.stderr || result.stdout}`);
    }
    return result.stdout.trim();
  }

  async getForkPointGitDetails() {
    await this.ensureGitRepo();
    const script = [
      'head=$(git -C /workspace rev-parse HEAD)',
      'subject=$(git -C /workspace log -1 --pretty=%s)',
      'parents=$(git -C /workspace rev-list --parents -n 1 HEAD)',
      'if git -C /workspace rev-parse HEAD^ >/dev/null 2>&1; then base=HEAD^; else base=$(git -C /workspace hash-object -t tree /dev/null); fi',
      'shortstat=$(git -C /workspace diff --shortstat "$base" HEAD)',
      'nameonly=$(git -C /workspace diff --name-only "$base" HEAD)',
      'numstat=$(git -C /workspace diff --numstat "$base" HEAD)',
      'patch=$(git -C /workspace diff --patch --stat --find-renames "$base" HEAD)',
      'printf "HEAD=%s\n" "$head"',
      'printf "SUBJECT=%s\n" "$subject"',
      'printf "PARENTS=%s\n" "$parents"',
      'printf "SHORTSTAT<<EOF\n%s\nEOF\n" "$shortstat"',
      'printf "NAMEONLY<<EOF\n%s\nEOF\n" "$nameonly"',
      'printf "NUMSTAT<<EOF\n%s\nEOF\n" "$numstat"',
      'printf "PATCH<<EOF\n%s\nEOF\n" "$patch"',
    ].join('; ');

    const result = await this.exec(script);
    if (result.exitCode !== 0) {
      throw new Error(`fork-point git details failed for ${this.label}: ${result.stderr || result.stdout}`);
    }

    const stdout = result.stdout;
    const readBlock = (name) => {
      const match = stdout.match(new RegExp(`${name}<<EOF\\n([\\s\\S]*?)\\nEOF`));
      return match ? match[1].trim() : '';
    };

    return {
      head: (stdout.match(/^HEAD=(.*)$/m)?.[1] || '').trim(),
      subject: (stdout.match(/^SUBJECT=(.*)$/m)?.[1] || '').trim(),
      parents: (stdout.match(/^PARENTS=(.*)$/m)?.[1] || '').trim(),
      shortStat: readBlock('SHORTSTAT'),
      changedFiles: readBlock('NAMEONLY').split('\n').map((line) => line.trim()).filter(Boolean),
      numStat: readBlock('NUMSTAT').split('\n').map((line) => line.trim()).filter(Boolean),
      patch: clipText(readBlock('PATCH'), 16000),
    };
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

  async captureForkPoint(reason, extra = {}) {
    const [gitStatus, gitHead, gitDetails, latestSession] = await Promise.all([
      this.inspectGitStatus().catch(() => null),
      this.getGitHead().catch(() => null),
      this.getForkPointGitDetails().catch(() => null),
      this.getLatestSession().catch(() => null),
    ]);

    const sessionEntries = safeJsonlParse(latestSession?.content || '');
    const contextUsage = summarizeSessionUsage(sessionEntries);
    const latestEntry = sessionEntries.at(-1) || null;
    const forkPoint = {
      reason,
      capturedAt: Date.now(),
      slot: this.slot,
      label: this.label,
      agentUuid: this.agentUuid,
      git: {
        head: gitHead,
        shortHead: shortSha(gitHead),
        status: gitStatus,
        subject: gitDetails?.subject || null,
        parents: gitDetails?.parents || null,
        shortStat: gitDetails?.shortStat || null,
        changedFiles: gitDetails?.changedFiles || [],
        numStat: gitDetails?.numStat || [],
        patch: gitDetails?.patch || '',
      },
      session: {
        path: latestSession?.path || null,
        latestEntryId: latestEntry?.id || null,
        totalEntries: contextUsage.totalEntries,
        assistantMessages: contextUsage.assistantMessages,
        latestStopReason: contextUsage.latestStopReason,
      },
      contextUsage,
      ...extra,
    };

    this.lastForkPoint = forkPoint;
    await this.writeJson('/state/meta/fork-point.json', forkPoint);
    this.emit({
      type: 'fork_point_recorded',
      reason,
      path: '/state/meta/fork-point.json',
      forkPoint: {
        reason: forkPoint.reason,
        capturedAt: forkPoint.capturedAt,
        git: {
          shortHead: forkPoint.git.shortHead,
          shortStat: forkPoint.git.shortStat,
          changedFiles: forkPoint.git.changedFiles,
        },
        contextUsage: {
          totalTokens: forkPoint.contextUsage.totalTokens,
          latestResponseTokens: forkPoint.contextUsage.latestResponseTokens,
          assistantMessages: forkPoint.contextUsage.assistantMessages,
        },
      },
    });
    return forkPoint;
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
    this.agentUuid = `piagent_${randomUUID().replace(/-/g, '').slice(0, 16)}`;
    await this.start();
  }

  async stop() {
    if (this.ws) {
      try { this.ws.terminate(); } catch {}
      this.ws = null;
    }

    if (!this.container) return;

    const container = this.container;
    const name = this.containerName;

    try {
      await container.stop({ t: 1 });
    } catch {}

    try {
      await container.remove({ force: true });
    } catch {}

    for (let attempt = 0; attempt < 20; attempt += 1) {
      try {
        await docker.getContainer(container.id).inspect();
        await delay(250);
      } catch {
        break;
      }
    }

    this.emit({ type: 'worker_container_removed', containerName: name, agentUuid: this.agentUuid });
    this.container = null;
    this.containerName = '';
    this.sessionId = null;
  }
}

class BrowserSession {
  constructor() {
    this.id = randomUUID().replace(/-/g, '').slice(0, 12);
    this.workers = [];
    this.snapshotImages = new Set();
    this.wsClients = new Set();
    this.sseClients = new Set();
    this.eventLog = [];
    this.eventCounter = 0;
  }

  attachWebSocket(ws) {
    this.wsClients.add(ws);
  }

  detachWebSocket(ws) {
    this.wsClients.delete(ws);
  }

  attachSse(res) {
    this.sseClients.add(res);
  }

  detachSse(res) {
    this.sseClients.delete(res);
  }

  emit(payload) {
    const eventRecord = {
      id: ++this.eventCounter,
      timestamp: Date.now(),
      payload,
    };
    this.eventLog.push(eventRecord);
    if (this.eventLog.length > 2000) this.eventLog.shift();

    for (const ws of this.wsClients) sendJson(ws, payload);
    for (const res of this.sseClients) {
      try {
        writeSseEvent(res, payload, eventRecord.id);
      } catch {}
    }
  }

  async initialize() {
    this.emit({ type: 'grid_boot', session: this.id, gridSize: 0, model: PI_MODEL, mergeModel: MERGE_MODEL });
    this.emit({ type: 'grid_ready', session: this.id, gridSize: 0, model: PI_MODEL });
  }

  getWorker(slot) {
    if (!Number.isInteger(slot) || slot < 0 || slot >= this.workers.length || !this.workers[slot]) {
      throw new Error(`Invalid slot: ${slot}`);
    }
    return this.workers[slot];
  }

  serializeWorker(worker) {
    return {
      slot: worker.slot,
      label: worker.label,
      agentUuid: worker.agentUuid,
      containerName: worker.containerName || null,
      sessionId: worker.sessionId || null,
      sourceImage: worker.sourceImage,
      status: worker.container ? 'running' : 'stopped',
      lastGitStatus: worker.lastGitStatus || null,
      lastForkPoint: worker.lastForkPoint || null,
    };
  }

  toJSON() {
    return {
      sessionId: this.id,
      model: PI_MODEL,
      mergeModel: MERGE_MODEL,
      instanceCount: this.workers.filter(Boolean).length,
      instances: this.workers.map((worker) => (worker ? this.serializeWorker(worker) : null)).filter(Boolean),
    };
  }

  async createInstance(sourceImage = WORKER_IMAGE) {
    const slot = this.workers.length;
    const worker = new WorkerHandle(this, slot, sourceImage);
    this.workers.push(worker);
    await worker.start();
    await worker.inspectGitStatus().catch((error) => worker.emit({ type: 'git_status_error', message: error.message }));
    this.emit({ type: 'instance_created', slot, label: worker.label, agentUuid: worker.agentUuid });
    return worker;
  }

  prompt(slot, message) {
    this.getWorker(slot).send({ type: 'prompt', message });
    return { accepted: true, slot, queuedAt: Date.now() };
  }

  async stopInstance(slot) {
    const worker = this.getWorker(slot);
    const label = worker.label;
    const agentUuid = worker.agentUuid;
    await worker.stop();
    this.workers[slot] = null;
    this.emit({ type: 'instance_stopped', slot, label, agentUuid });
    return { slot, label, agentUuid };
  }

  async fork(sourceSlot) {
    const source = this.getWorker(sourceSlot);
    this.emit({ type: 'fork_start', sourceSlot, sourceLabel: source.label });
    const forkPoint = await source.captureForkPoint('fork');
    const image = await source.commitSnapshot();
    const target = await this.createInstance(image);
    const result = { sourceSlot, targetSlot: target.slot, targetLabel: target.label, image, forkPoint };
    this.emit({ type: 'fork_complete', ...result });
    return result;
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
    const result = {
      sourceSlot,
      targetSlot,
      remoteName: imported.remoteName,
      bytes: bundle.length,
      nextStep: `git -C /workspace merge ${remoteName}/main || git -C /workspace log --oneline --all --graph`,
    };
    this.emit({ type: 'merge_prep_complete', ...result });
    return result;
  }

  async merge(sourceSlot, targetSlot) {
    if (sourceSlot === targetSlot) throw new Error('Source and target slots must differ');
    const source = this.getWorker(sourceSlot);
    const target = this.getWorker(targetSlot);
    const remoteName = `merge_slot_${sourceSlot + 1}`;

    this.emit({ type: 'merge_start', sourceSlot, targetSlot, sourceLabel: source.label, targetLabel: target.label });

    const forkPoint = await target.captureForkPoint('merge integration base', { mergeSourceSlot: sourceSlot, mergeTargetSlot: targetSlot });
    const integrationImage = await target.commitSnapshot();
    const integration = await this.createInstance(integrationImage);
    const integrationSlot = integration.slot;

    this.emit({
      type: 'merge_integration_created',
      sourceSlot,
      targetSlot,
      integrationSlot,
      integrationLabel: integration.label,
      integrationAgentUuid: integration.agentUuid,
      image: integrationImage,
      forkPoint,
    });

    const bundle = await source.exportBundle();
    await integration.importBundle(bundle, remoteName);
    const mergeResult = await integration.mergeFetchedRemote(remoteName, 'main');
    const [sourceSession, targetSession] = await Promise.all([
      source.getLatestSession().catch(() => null),
      target.getLatestSession().catch(() => null),
    ]);

    const mergeContext = await summarizeMergedContext({
      source: { label: source.label, session: sourceSession },
      target: { label: target.label, session: targetSession },
      mergeResult,
    });

    await integration.writeMergeContext(mergeContext, {
      sourceSlot,
      targetSlot,
      integrationSlot,
      remoteName,
      mergeExitCode: mergeResult.exitCode,
      sourceSessionPath: sourceSession?.path || null,
      targetSessionPath: targetSession?.path || null,
      mergeStdout: mergeResult.stdout,
      mergeStderr: mergeResult.stderr,
    });

    await integration.inspectGitStatus().catch((error) => integration.emit({ type: 'git_status_error', message: error.message }));
    const result = {
      sourceSlot,
      targetSlot,
      integrationSlot,
      remoteName,
      mergeExitCode: mergeResult.exitCode,
      mergeContextPath: '/state/meta/merge-context.md',
    };
    this.emit({ type: 'merge_complete', ...result });
    return result;
  }

  async dispose() {
    await Promise.all(this.workers.filter(Boolean).map((worker) => worker.stop().catch(() => {})));
    await Promise.all([...this.snapshotImages].map(async (image) => {
      try {
        await docker.getImage(image).remove({ force: true });
      } catch {}
    }));
  }
}

const orchestrator = new BrowserSession();
const publicDir = path.join(__dirname, 'public');

async function handleApiRequest(req, res, url) {
  const method = req.method || 'GET';
  const parts = url.pathname.split('/').filter(Boolean);

  try {
    if (parts[0] !== 'api') {
      return sendApiError(res, 404, 'NOT_FOUND', 'Unknown API route');
    }

    if (method === 'GET' && parts[1] === 'state') {
      return sendJsonResponse(res, 200, orchestrator.toJSON());
    }

    if (method === 'GET' && parts[1] === 'events' && parts[2] === 'stream') {
      startSse(res);
      orchestrator.attachSse(res);
      for (const event of orchestrator.eventLog) writeSseEvent(res, event.payload, event.id);
      req.on('close', () => orchestrator.detachSse(res));
      return;
    }

    if (parts[1] === 'instances' && method === 'POST' && parts.length === 2) {
      const worker = await orchestrator.createInstance();
      return sendJsonResponse(res, 201, {
        slot: worker.slot,
        label: worker.label,
        agentUuid: worker.agentUuid,
      });
    }

    if (parts[1] === 'instances' && method === 'GET' && parts.length === 2) {
      return sendJsonResponse(res, 200, { instances: orchestrator.toJSON().instances });
    }

    if (parts[1] === 'instances' && parts.length >= 3) {
      const slot = Number(parts[2]);
      if (!Number.isInteger(slot)) return sendApiError(res, 400, 'BAD_REQUEST', 'slot must be an integer');

      if (method === 'GET' && parts.length === 3) {
        const worker = orchestrator.getWorker(slot);
        return sendJsonResponse(res, 200, orchestrator.serializeWorker(worker));
      }

      if (method === 'POST' && parts[3] === 'prompt') {
        const body = await readJsonBody(req);
        if (!body.message || typeof body.message !== 'string') {
          return sendApiError(res, 400, 'BAD_REQUEST', 'message is required');
        }
        return sendJsonResponse(res, 202, orchestrator.prompt(slot, body.message));
      }

      if (method === 'GET' && parts[3] === 'artifacts' && parts[4] === 'fork-point') {
        const worker = orchestrator.getWorker(slot);
        try {
          return sendJsonResponse(res, 200, await worker.readJsonFile('/state/meta/fork-point.json'));
        } catch (error) {
          return sendApiError(res, 404, 'ARTIFACT_NOT_FOUND', error.message);
        }
      }

      if (method === 'GET' && parts[3] === 'artifacts' && parts[4] === 'merge-details') {
        const worker = orchestrator.getWorker(slot);
        try {
          return sendJsonResponse(res, 200, await worker.readJsonFile('/state/meta/merge-details.json'));
        } catch (error) {
          return sendApiError(res, 404, 'ARTIFACT_NOT_FOUND', error.message);
        }
      }

      if (method === 'GET' && parts[3] === 'artifacts' && parts[4] === 'merge-context') {
        const worker = orchestrator.getWorker(slot);
        try {
          return sendTextResponse(res, 200, await worker.readTextFile('/state/meta/merge-context.md'), 'text/markdown; charset=utf-8');
        } catch (error) {
          return sendApiError(res, 404, 'ARTIFACT_NOT_FOUND', error.message);
        }
      }

      if (method === 'POST' && parts[3] === 'fork') {
        return sendJsonResponse(res, 200, await orchestrator.fork(slot));
      }

      if (method === 'POST' && parts[3] === 'stop') {
        return sendJsonResponse(res, 200, { ok: true, ...(await orchestrator.stopInstance(slot)) });
      }
    }

    if (method === 'POST' && parts[1] === 'merge-prep') {
      const body = await readJsonBody(req);
      return sendJsonResponse(res, 200, await orchestrator.prepareMergeBundle(body.sourceSlot, body.targetSlot));
    }

    if (method === 'POST' && parts[1] === 'merge') {
      const body = await readJsonBody(req);
      return sendJsonResponse(res, 200, await orchestrator.merge(body.sourceSlot, body.targetSlot));
    }

    return sendApiError(res, 404, 'NOT_FOUND', 'Unknown API route');
  } catch (error) {
    const statusCode = /Invalid slot/.test(error.message) ? 404 : 500;
    const code = /Invalid slot/.test(error.message) ? 'INVALID_SLOT' : 'INTERNAL_ERROR';
    return sendApiError(res, statusCode, code, error.message);
  }
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

    if (url.pathname.startsWith('/api/')) {
      return await handleApiRequest(req, res, url);
    }

    const reqPath = url.pathname === '/' ? '/index.html' : url.pathname;
    const filePath = path.join(publicDir, path.normalize(reqPath));

    if (!filePath.startsWith(publicDir)) {
      return sendTextResponse(res, 403, 'Forbidden');
    }

    fs.readFile(filePath, (err, content) => {
      if (err) {
        sendTextResponse(res, 404, 'Not found');
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

      sendTextResponse(res, 200, content, type);
    });
  } catch (error) {
    sendApiError(res, 500, 'INTERNAL_ERROR', error.message);
  }
});

const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
  orchestrator.attachWebSocket(ws);
  sendJson(ws, { type: 'grid_boot', session: orchestrator.id, gridSize: 0, model: PI_MODEL, mergeModel: MERGE_MODEL });
  sendJson(ws, { type: 'grid_ready', session: orchestrator.id, gridSize: 0, model: PI_MODEL });

  ws.on('message', async (buffer) => {
    try {
      const message = JSON.parse(buffer.toString('utf8'));
      if (message.type === 'create_instance') return await orchestrator.createInstance();
      if (message.type === 'prompt') return orchestrator.prompt(message.target, message.message);
      if (message.type === 'stop_instance') return await orchestrator.stopInstance(message.target);
      if (message.type === 'fork') return await orchestrator.fork(message.source);
      if (message.type === 'prepare_merge') return await orchestrator.prepareMergeBundle(message.source, message.target);
      if (message.type === 'merge') return await orchestrator.merge(message.source, message.target);
      sendJson(ws, { type: 'bridge_error', message: 'Unsupported client message' });
    } catch (error) {
      sendJson(ws, { type: 'bridge_error', message: error.message });
    }
  });

  ws.on('close', () => {
    orchestrator.detachWebSocket(ws);
  });
});

async function main() {
  await orchestrator.initialize();
  server.listen(PORT, () => {
    console.log(`orchestrator listening on http://0.0.0.0:${PORT}`);
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
