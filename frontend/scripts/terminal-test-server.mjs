#!/usr/bin/env node

import http from 'node:http';
import path from 'node:path';
import process from 'node:process';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket, WebSocketServer } from 'ws';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const bridgeScript = path.join(__dirname, 'pty-bridge.py');

const host = process.env.TERMINAL_HOST ?? '127.0.0.1';
const port = readNumber(process.env.TERMINAL_PORT, 8787);
const pathName = process.env.TERMINAL_PATH ?? '/terminal';
const cwd = process.env.TERMINAL_CWD ?? process.cwd();
const shell =
	process.env.TERMINAL_SHELL ??
	process.env.SHELL ??
	(process.platform === 'win32' ? process.env.ComSpec || 'powershell.exe' : '/bin/bash');
const shellArgs = (process.env.TERMINAL_SHELL_ARGS ?? '').split(' ').filter(Boolean);
const python = process.env.TERMINAL_PYTHON ?? 'python3';
const defaultCols = 120;
const defaultRows = 34;

const server = http.createServer((request, response) => {
	const requestUrl = new URL(
		request.url ?? '/',
		`http://${request.headers.host ?? `${host}:${port}`}`
	);

	response.writeHead(200, { 'content-type': 'text/plain; charset=utf-8' });
	response.end(
		[
			'Agents of Chaos terminal test backend',
			'',
			`WebSocket endpoint: ws://${host}:${port}${pathName}`,
			`Working directory: ${cwd}`,
			`Shell: ${shell}${shellArgs.length > 0 ? ` ${shellArgs.join(' ')}` : ''}`,
			`Python bridge: ${python} ${bridgeScript}`,
			'',
			requestUrl.pathname === pathName
				? 'Connect to this URL with a WebSocket client.'
				: `Open ${pathName} with a WebSocket client to start a PTY session.`
		].join('\n')
	);
});

const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (request, socket, head) => {
	const requestUrl = new URL(
		request.url ?? '/',
		`http://${request.headers.host ?? `${host}:${port}`}`
	);

	if (requestUrl.pathname !== pathName) {
		socket.write('HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n');
		socket.destroy();
		return;
	}

	wss.handleUpgrade(request, socket, head, (websocket) => {
		wss.emit('connection', websocket, request);
	});
});

wss.on('connection', (websocket, request) => {
	const requestUrl = new URL(
		request.url ?? '/',
		`http://${request.headers.host ?? `${host}:${port}`}`
	);
	const cols = clampNumber(requestUrl.searchParams.get('cols'), defaultCols, 40, 320);
	const rows = clampNumber(requestUrl.searchParams.get('rows'), defaultRows, 12, 120);
	const bridge = spawn(
		python,
		[
			bridgeScript,
			'--shell',
			shell,
			'--cwd',
			cwd,
			'--cols',
			String(cols),
			'--rows',
			String(rows),
			...shellArgs.flatMap((value) => ['--shell-arg', value])
		],
		{
			stdio: ['pipe', 'pipe', 'inherit', 'pipe']
		}
	);
	const controlChannel = bridge.stdio[3];

	if (!controlChannel) {
		websocket.close(1011, 'missing PTY control channel');
		bridge.kill();
		return;
	}

	console.log(
		`pty session opened (${cols}x${rows}) from ${request.socket.remoteAddress ?? 'unknown client'}`
	);

	bridge.stdout.on('data', (chunk) => {
		if (websocket.readyState === WebSocket.OPEN) {
			websocket.send(chunk);
		}
	});

	bridge.on('error', (error) => {
		console.error('pty bridge error:', error);
		if (websocket.readyState === WebSocket.OPEN) {
			websocket.send(`\r\n\x1b[31m[pty bridge error: ${error.message}]\x1b[0m\r\n`);
			websocket.close(1011, 'pty bridge failed');
		}
	});

	bridge.on('exit', (exitCode, signal) => {
		if (websocket.readyState === WebSocket.OPEN) {
			websocket.send(
				`\r\n\x1b[2m[process exited with code ${exitCode ?? 'null'}${signal ? `, signal ${signal}` : ''}]\x1b[0m\r\n`
			);
			websocket.close();
		}
	});

	websocket.on('message', (payload, isBinary) => {
		if (!isBinary) {
			const text = payload.toString();
			const resize = parseResizeMessage(text);
			if (resize) {
				controlChannel.write(`${JSON.stringify(resize)}\n`);
				return;
			}

			bridge.stdin.write(text);
			return;
		}

		bridge.stdin.write(Buffer.from(payload));
	});

	websocket.on('close', () => {
		bridge.kill('SIGTERM');
		console.log('pty session closed');
	});

	websocket.on('error', (error) => {
		console.error('websocket error:', error);
		bridge.kill('SIGTERM');
	});
});

server.listen(port, host, () => {
	console.log('terminal test backend ready');
	console.log(`  http://${host}:${port}`);
	console.log(`  ws://${host}:${port}${pathName}`);
	console.log(`  shell: ${shell}${shellArgs.length > 0 ? ` ${shellArgs.join(' ')}` : ''}`);
	console.log(`  cwd: ${cwd}`);
	console.log(`  python: ${python}`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
	process.on(signal, () => {
		console.log(`\nreceived ${signal}, shutting down...`);
		wss.close(() => {
			server.close(() => {
				process.exit(0);
			});
		});
	});
}

/**
 * @param {string | undefined} value
 * @param {number} fallback
 */
function readNumber(value, fallback) {
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * @param {string | null} value
 * @param {number} fallback
 * @param {number} minimum
 * @param {number} maximum
 */
function clampNumber(value, fallback, minimum, maximum) {
	const parsed = Number(value);
	if (!Number.isFinite(parsed)) return fallback;
	return Math.min(maximum, Math.max(minimum, Math.floor(parsed)));
}

/**
 * @param {string} value
 */
function parseResizeMessage(value) {
	if (!value.startsWith('{')) return null;

	try {
		const message = JSON.parse(value);
		if (message?.type !== 'resize') return null;
		if (typeof message.cols !== 'number' || typeof message.rows !== 'number') return null;

		return {
			type: 'resize',
			cols: clampNumber(String(message.cols), defaultCols, 40, 320),
			rows: clampNumber(String(message.rows), defaultRows, 12, 120)
		};
	} catch {
		return null;
	}
}
