const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { randomUUID } = require('crypto');
const { WebSocketServer } = require('ws');
const { StringDecoder } = require('string_decoder');

const PORT = Number(process.env.PORT || 3000);
const PI_WORKSPACE = process.env.PI_WORKSPACE || '/workspace';
const PI_MODEL = process.env.PI_MODEL || 'openai/gpt-4o-mini';
const GRID_SIZE = 4;

function sendJson(ws, payload) {
  if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(payload));
}

function attachJsonlReader(stream, onLine) {
  const decoder = new StringDecoder('utf8');
  let buffer = '';

  stream.on('data', (chunk) => {
    buffer += typeof chunk === 'string' ? chunk : decoder.write(chunk);

    while (true) {
      const newlineIndex = buffer.indexOf('\n');
      if (newlineIndex === -1) break;

      let line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      if (line.endsWith('\r')) line = line.slice(0, -1);
      if (line.length > 0) onLine(line);
    }
  });

  stream.on('end', () => {
    buffer += decoder.end();
    const line = buffer.endsWith('\r') ? buffer.slice(0, -1) : buffer;
    if (line.length > 0) onLine(line);
  });
}

class PiRpcSession {
  constructor(ws, index) {
    this.ws = ws;
    this.index = index;
    this.label = `pi-${index + 1}`;
    this.id = randomUUID();
    this.currentAssistantText = '';
    this.spawnPi();
  }

  emit(payload) {
    sendJson(this.ws, {
      sessionId: this.id,
      index: this.index,
      label: this.label,
      ...payload,
    });
  }

  writeTerminal(text) {
    this.emit({ type: 'session_output', text });
  }

  spawnPi() {
    const args = ['--mode', 'rpc', '--no-session', '--model', PI_MODEL];
    this.proc = spawn('node_modules/.bin/pi', args, {
      cwd: PI_WORKSPACE,
      env: process.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    attachJsonlReader(this.proc.stdout, (line) => {
      try {
        const event = JSON.parse(line);

        if (event.type === 'agent_start') {
          this.currentAssistantText = '';
          this.writeTerminal('\n> agent started\n');
        }

        if (event.type === 'message_update' && event.assistantMessageEvent?.type === 'text_delta') {
          this.currentAssistantText += event.assistantMessageEvent.delta;
          this.emit({
            type: 'assistant_delta',
            delta: event.assistantMessageEvent.delta,
            text: this.currentAssistantText,
          });
          this.writeTerminal(event.assistantMessageEvent.delta);
        }

        if (event.type === 'tool_execution_start') {
          this.writeTerminal(`\n$ tool ${event.toolName} ${JSON.stringify(event.args)}\n`);
        }

        if (event.type === 'tool_execution_end') {
          const content = Array.isArray(event.result?.content)
            ? event.result.content
                .filter((item) => item.type === 'text')
                .map((item) => item.text)
                .join('\n')
            : '';
          this.writeTerminal(`\n$ tool ${event.toolName} ${event.isError ? 'failed' : 'done'}\n`);
          if (content) this.writeTerminal(`${content}\n`);
        }

        if (event.type === 'message_end' && event.message?.role === 'assistant') {
          this.writeTerminal('\n');
        }

        if (event.type === 'response' && event.command === 'prompt' && event.success) {
          this.writeTerminal('> prompt accepted\n');
        }

        this.emit({ type: 'pi_event', event });
      } catch (error) {
        this.emit({ type: 'bridge_error', message: `Failed to parse pi output: ${error.message}`, raw: line });
      }
    });

    attachJsonlReader(this.proc.stderr, (line) => {
      this.emit({ type: 'pi_stderr', line });
      this.writeTerminal(`\n! stderr ${line}\n`);
    });

    this.proc.on('exit', (code, signal) => {
      this.emit({ type: 'session_exit', code, signal });
      this.writeTerminal(`\n! exited code=${code ?? 'null'} signal=${signal ?? 'none'}\n`);
    });

    this.emit({
      type: 'session_ready',
      model: PI_MODEL,
      workspace: PI_WORKSPACE,
    });
    this.writeTerminal(`> ${this.label} ready (${PI_MODEL}) in ${PI_WORKSPACE}\n`);
  }

  send(command) {
    if (!this.proc || this.proc.killed) throw new Error('pi process is not running');
    this.proc.stdin.write(`${JSON.stringify(command)}\n`);
  }

  prompt(message) {
    this.writeTerminal(`\n> user ${message}\n`);
    this.send({ id: randomUUID(), type: 'prompt', message });
  }

  abort() {
    this.writeTerminal('\n> abort requested\n');
    this.send({ id: randomUUID(), type: 'abort' });
  }

  dispose() {
    if (!this.proc || this.proc.killed) return;
    this.proc.kill('SIGTERM');
  }
}

function getSessionByTarget(sessions, target) {
  if (typeof target !== 'number' || !Number.isInteger(target) || target < 0 || target >= sessions.length) {
    throw new Error(`Invalid target index: ${target}`);
  }
  return sessions[target];
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

wss.on('connection', (ws) => {
  const sessions = Array.from({ length: GRID_SIZE }, (_, index) => new PiRpcSession(ws, index));
  sendJson(ws, { type: 'grid_ready', gridSize: GRID_SIZE, model: PI_MODEL, workspace: PI_WORKSPACE });

  ws.on('message', (buffer) => {
    try {
      const message = JSON.parse(buffer.toString('utf8'));

      if (message.type === 'prompt') {
        getSessionByTarget(sessions, message.target).prompt(message.message);
        return;
      }

      if (message.type === 'prompt_all') {
        sessions.forEach((session) => session.prompt(message.message));
        return;
      }

      if (message.type === 'abort') {
        getSessionByTarget(sessions, message.target).abort();
        return;
      }

      if (message.type === 'abort_all') {
        sessions.forEach((session) => session.abort());
        return;
      }

      if (message.type === 'raw_rpc' && message.command && typeof message.command === 'object') {
        getSessionByTarget(sessions, message.target).send({ id: randomUUID(), ...message.command });
        return;
      }

      sendJson(ws, { type: 'bridge_error', message: 'Unsupported client message' });
    } catch (error) {
      sendJson(ws, { type: 'bridge_error', message: error.message });
    }
  });

  ws.on('close', () => {
    sessions.forEach((session) => session.dispose());
  });
});

server.listen(PORT, () => {
  console.log(`pi rpc bridge listening on http://0.0.0.0:${PORT}`);
});
