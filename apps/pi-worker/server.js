const http = require('http');
const path = require('path');
const { spawn } = require('child_process');
const { randomUUID } = require('crypto');
const { WebSocketServer } = require('ws');
const { StringDecoder } = require('string_decoder');

const PORT = Number(process.env.PORT || 3000);
const PI_WORKSPACE = process.env.PI_WORKSPACE || '/workspace';
const PI_MODEL = process.env.PI_MODEL || 'openai/gpt-4o-mini';
const INSTANCE_LABEL = process.env.INSTANCE_LABEL || 'pi-worker';
const PI_AGENT_UUID = process.env.PI_AGENT_UUID || 'piagent_local';
const PI_AGENT_DIR = process.env.PI_CODING_AGENT_DIR || '/state/pi-agent';
const PI_BIN = process.env.PI_BIN || path.join(__dirname, 'node_modules/.bin/pi');

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
  constructor() {
    this.id = randomUUID();
    this.currentAssistantText = '';
    this.clients = new Set();
    this.spawnPi();
  }

  broadcast(payload) {
    for (const ws of this.clients) sendJson(ws, payload);
  }

  writeTerminal(text) {
    this.broadcast({ type: 'session_output', text });
  }

  spawnPi() {
    const args = ['--mode', 'rpc', '--model', PI_MODEL];
    this.proc = spawn(PI_BIN, args, {
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
          this.broadcast({
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
            ? event.result.content.filter((item) => item.type === 'text').map((item) => item.text).join('\n')
            : '';
          this.writeTerminal(`\n$ tool ${event.toolName} ${event.isError ? 'failed' : 'done'}\n`);
          if (content) this.writeTerminal(`${content}\n`);
        }

        if (event.type === 'message_end' && event.message?.role === 'assistant') {
          this.writeTerminal('\n');
        }

        this.broadcast({ type: 'pi_event', event });
      } catch (error) {
        this.broadcast({ type: 'bridge_error', message: `Failed to parse pi output: ${error.message}`, raw: line });
      }
    });

    this.proc.on('error', (error) => {
      this.broadcast({ type: 'bridge_error', message: `Failed to start pi: ${error.message}` });
      this.writeTerminal(`\n! failed to start pi: ${error.message}\n`);
    });

    attachJsonlReader(this.proc.stderr, (line) => {
      this.broadcast({ type: 'pi_stderr', line });
      this.writeTerminal(`\n! stderr ${line}\n`);
    });

    this.proc.on('exit', (code, signal) => {
      this.broadcast({ type: 'session_exit', code, signal });
      this.writeTerminal(`\n! exited code=${code ?? 'null'} signal=${signal ?? 'none'}\n`);
    });
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

  register(ws) {
    this.clients.add(ws);
    sendJson(ws, {
      type: 'session_ready',
      sessionId: this.id,
      model: PI_MODEL,
      workspace: PI_WORKSPACE,
      agentDir: PI_AGENT_DIR,
      label: INSTANCE_LABEL,
      agentUuid: PI_AGENT_UUID,
    });
    sendJson(ws, { type: 'session_output', text: `> ${INSTANCE_LABEL} ready (${PI_MODEL}) in ${PI_WORKSPACE} [${PI_AGENT_UUID}]\n` });
  }

  unregister(ws) {
    this.clients.delete(ws);
  }

  dispose() {
    if (!this.proc || this.proc.killed) return;
    this.proc.kill('SIGTERM');
  }
}

const session = new PiRpcSession();
const server = http.createServer((_req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ ok: true, label: INSTANCE_LABEL, model: PI_MODEL }));
});

const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
  session.register(ws);

  ws.on('message', (buffer) => {
    try {
      const message = JSON.parse(buffer.toString('utf8'));
      if (message.type === 'prompt') return session.prompt(message.message);
      if (message.type === 'abort') return session.abort();
      if (message.type === 'raw_rpc' && message.command && typeof message.command === 'object') {
        return session.send({ id: randomUUID(), ...message.command });
      }
      sendJson(ws, { type: 'bridge_error', message: 'Unsupported client message' });
    } catch (error) {
      sendJson(ws, { type: 'bridge_error', message: error.message });
    }
  });

  ws.on('close', () => session.unregister(ws));
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    session.dispose();
    server.close(() => process.exit(0));
  });
}

server.listen(PORT, () => {
  console.log(`pi worker listening on http://0.0.0.0:${PORT}`);
});
