<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount, tick } from 'svelte';
	import type { FitAddon as XtermFitAddon } from '@xterm/addon-fit';
	import type { ITerminalOptions, Terminal as XtermTerminal } from '@xterm/xterm';
	import '@xterm/xterm/css/xterm.css';

	type SocketState = 'idle' | 'connecting' | 'open' | 'closed' | 'error';
	type SocketMessage =
		| { type: 'input'; data: string }
		| { type: 'resize'; cols: number; rows: number };
	type OutgoingPayload = string | ArrayBuffer | Blob | ArrayBufferView;
	type EncodeOutgoing = (message: SocketMessage) => OutgoingPayload;
	type DecodeIncoming = (
		data: MessageEvent['data']
	) => string | Uint8Array | null | Promise<string | Uint8Array | null>;
	interface Props {
		wsUrl: string;
		protocols?: string | string[];
		connectOnMount?: boolean;
		reconnect?: boolean;
		reconnectDelay?: number;
		title?: string;
		termOptions?: ITerminalOptions;
		encodeOutgoing?: EncodeOutgoing;
		decodeIncoming?: DecodeIncoming;
		onStatusChange?: (status: SocketState) => void;
	}

	const ghosttyTheme: NonNullable<ITerminalOptions['theme']> = {
		background: '#0f141b',
		foreground: '#d8dee9',
		cursor: '#f8fafc',
		cursorAccent: '#0f141b',
		selectionBackground: '#2e4057',
		selectionInactiveBackground: '#233041',
		black: '#111827',
		red: '#f87171',
		green: '#4ade80',
		yellow: '#fbbf24',
		blue: '#60a5fa',
		magenta: '#c084fc',
		cyan: '#22d3ee',
		white: '#e5e7eb',
		brightBlack: '#6b7280',
		brightRed: '#fb7185',
		brightGreen: '#86efac',
		brightYellow: '#fde68a',
		brightBlue: '#93c5fd',
		brightMagenta: '#d8b4fe',
		brightCyan: '#67e8f9',
		brightWhite: '#f8fafc'
	};

	const defaultEncodeOutgoing: EncodeOutgoing = (message) => {
		if (message.type === 'input') return message.data;

		return JSON.stringify({
			type: 'resize',
			cols: message.cols,
			rows: message.rows
		});
	};

	const defaultDecodeIncoming: DecodeIncoming = async (data) => {
		if (typeof data === 'string') return data;
		if (data instanceof ArrayBuffer) return new Uint8Array(data);
		if (data instanceof Blob) return new Uint8Array(await data.arrayBuffer());
		if (ArrayBuffer.isView(data))
			return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);

		return null;
	};

	let {
		wsUrl,
		protocols,
		connectOnMount = true,
		reconnect = true,
		reconnectDelay = 1_500,
		title = 'Terminal stream',
		termOptions = {},
		encodeOutgoing = defaultEncodeOutgoing,
		decodeIncoming = defaultDecodeIncoming,
		onStatusChange
	}: Props = $props();

	let terminalHost = $state<HTMLDivElement | null>(null);
	let terminal = $state<XtermTerminal | null>(null);
	let fitAddon = $state<XtermFitAddon | null>(null);
	let socket = $state<WebSocket | null>(null);
	let resizeObserver = $state<ResizeObserver | null>(null);
	let socketState = $state<SocketState>('idle');
	let mounted = $state(false);
	let manualDisconnect = false;
	let lastConnectedUrl = $state('');
	let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	let fitFrame = 0;
	let defaultFontSize = $state(14);
	let currentFontSize = $state(14);

	const statusClasses: Record<SocketState, string> = {
		idle: 'border-white/10 bg-white/5 text-slate-300',
		connecting: 'border-sky-400/30 bg-sky-400/10 text-sky-200',
		open: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
		closed: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
		error: 'border-rose-400/30 bg-rose-400/10 text-rose-200'
	};

	const shortcutHints = [
		'⌘C / Ctrl+Shift+C copy',
		'⌘V / Ctrl+Shift+V paste',
		'⌘A / Ctrl+A select all',
		'⌘K / Ctrl+K clear',
		'⌘± / Ctrl± zoom',
		'Shift+PgUp/PgDn scroll'
	];

	function setSocketState(next: SocketState) {
		socketState = next;
		onStatusChange?.(next);
	}

	function isApplePlatform() {
		if (!browser) return false;

		return /(Mac|iPhone|iPad|iPod)/i.test(navigator.platform);
	}

	function preventAndStop(event: KeyboardEvent) {
		event.preventDefault();
		event.stopPropagation();
	}

	async function copySelection() {
		const selection = terminal?.getSelection() ?? '';
		if (!selection || !navigator.clipboard) return;

		try {
			await navigator.clipboard.writeText(selection);
		} catch {
			// Ignore clipboard API errors in non-secure contexts.
		}
	}

	async function pasteFromClipboard() {
		if (!navigator.clipboard) return;

		try {
			const text = await navigator.clipboard.readText();
			if (!text) return;

			sendMessage({ type: 'input', data: text });
		} catch {
			// Ignore clipboard API errors in non-secure contexts.
		}
	}

	function requestFit() {
		if (!browser) return;

		cancelAnimationFrame(fitFrame);
		fitFrame = requestAnimationFrame(() => {
			if (!terminal || !fitAddon) return;

			fitAddon.fit();
			sendResize();
		});
	}

	function updateFontSize(nextFontSize: number) {
		currentFontSize = Math.max(10, Math.min(24, nextFontSize));
		if (terminal) {
			terminal.options.fontSize = currentFontSize;
			requestFit();
		}
	}

	function clearReconnectTimer() {
		if (reconnectTimer) {
			clearTimeout(reconnectTimer);
			reconnectTimer = null;
		}
	}

	function closeSocket() {
		if (!socket) return;

		socket.onopen = null;
		socket.onclose = null;
		socket.onerror = null;
		socket.onmessage = null;
		if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
			socket.close();
		}
		socket = null;
	}

	function scheduleReconnect() {
		if (!browser || !reconnect || manualDisconnect || !wsUrl) return;

		clearReconnectTimer();
		reconnectTimer = setTimeout(() => {
			connect();
		}, reconnectDelay);
	}

	function createTerminalOptions(): ITerminalOptions {
		return {
			allowTransparency: true,
			bellStyle: 'none',
			convertEol: false,
			cursorBlink: true,
			cursorInactiveStyle: 'outline',
			cursorStyle: 'block',
			disableStdin: false,
			drawBoldTextInBrightColors: true,
			fontFamily:
				'"Berkeley Mono", "JetBrains Mono", "SFMono-Regular", Menlo, Monaco, Consolas, monospace',
			fontSize: currentFontSize,
			fontWeight: 400,
			fontWeightBold: 700,
			lineHeight: 1.22,
			macOptionIsMeta: true,
			minimumContrastRatio: 1.2,
			rightClickSelectsWord: true,
			scrollback: 25_000,
			smoothScrollDuration: 0,
			tabStopWidth: 4,
			theme: {
				...ghosttyTheme,
				...termOptions.theme
			},
			...termOptions
		} as ITerminalOptions & { bellStyle?: 'none' };
	}

	function sendRaw(payload: OutgoingPayload) {
		if (socket?.readyState !== WebSocket.OPEN) return;

		if (typeof payload === 'string' || payload instanceof Blob || payload instanceof ArrayBuffer) {
			socket.send(payload);
			return;
		}

		const bytes = new Uint8Array(payload.byteLength);
		bytes.set(
			new Uint8Array(payload.buffer as ArrayBuffer, payload.byteOffset, payload.byteLength)
		);
		socket.send(bytes);
	}

	function sendMessage(message: SocketMessage) {
		sendRaw(encodeOutgoing(message));
	}

	function sendResize() {
		if (!terminal || terminal.cols === 0 || terminal.rows === 0) return;
		sendMessage({ type: 'resize', cols: terminal.cols, rows: terminal.rows });
	}

	async function handleIncoming(data: MessageEvent['data']) {
		const payload = await decodeIncoming(data);
		if (!payload || !terminal) return;

		terminal.write(payload);
	}

	function focusTerminal() {
		terminal?.focus();
	}

	function clearTerminal() {
		terminal?.clear();
		focusTerminal();
	}

	function handleTerminalHostKeydown(event: KeyboardEvent) {
		if (event.target !== event.currentTarget) return;
		if (event.key !== 'Enter' && event.key !== ' ') return;

		event.preventDefault();
		focusTerminal();
	}

	function connect() {
		if (!browser || !wsUrl || !terminal) return;

		manualDisconnect = false;
		clearReconnectTimer();
		closeSocket();
		setSocketState('connecting');
		lastConnectedUrl = wsUrl;

		const nextSocket = protocols ? new WebSocket(wsUrl, protocols) : new WebSocket(wsUrl);
		nextSocket.binaryType = 'arraybuffer';
		nextSocket.onopen = () => {
			socket = nextSocket;
			setSocketState('open');
			requestFit();
			focusTerminal();
		};
		nextSocket.onmessage = async (event) => {
			await handleIncoming(event.data);
		};
		nextSocket.onerror = () => {
			setSocketState('error');
		};
		nextSocket.onclose = () => {
			socket = null;
			setSocketState('closed');
			scheduleReconnect();
		};
		socket = nextSocket;
	}

	function disconnect(manual = true) {
		manualDisconnect = manual;
		clearReconnectTimer();
		closeSocket();
		setSocketState('closed');
	}

	function installKeyboardShortcuts(instance: XtermTerminal) {
		instance.attachCustomKeyEventHandler((event) => {
			if (event.type !== 'keydown') return true;

			const lower = event.key.toLowerCase();
			const isApple = isApplePlatform();
			const primaryModifier = isApple ? event.metaKey : event.ctrlKey;
			const copyPressed =
				(isApple && event.metaKey && !event.ctrlKey && lower === 'c') ||
				(!isApple && event.ctrlKey && event.shiftKey && lower === 'c');
			const pastePressed =
				(isApple && event.metaKey && !event.ctrlKey && lower === 'v') ||
				(!isApple && event.ctrlKey && event.shiftKey && lower === 'v') ||
				(!isApple && event.shiftKey && event.key === 'Insert');

			if (copyPressed) {
				preventAndStop(event);
				void copySelection();
				return false;
			}

			if (pastePressed) {
				preventAndStop(event);
				void pasteFromClipboard();
				return false;
			}

			if (primaryModifier && lower === 'a') {
				preventAndStop(event);
				instance.selectAll();
				return false;
			}

			if (primaryModifier && lower === 'k') {
				preventAndStop(event);
				clearTerminal();
				return false;
			}

			if (primaryModifier && (event.key === '+' || event.key === '=')) {
				preventAndStop(event);
				updateFontSize(currentFontSize + 1);
				return false;
			}

			if (primaryModifier && event.key === '-') {
				preventAndStop(event);
				updateFontSize(currentFontSize - 1);
				return false;
			}

			if (primaryModifier && event.key === '0') {
				preventAndStop(event);
				updateFontSize(defaultFontSize);
				return false;
			}

			if (event.shiftKey && event.key === 'PageUp') {
				preventAndStop(event);
				instance.scrollLines(-(instance.rows - 1));
				return false;
			}

			if (event.shiftKey && event.key === 'PageDown') {
				preventAndStop(event);
				instance.scrollLines(instance.rows - 1);
				return false;
			}

			return true;
		});
	}

	onMount(() => {
		if (!browser || !terminalHost) return;

		let disposed = false;
		let instance: XtermTerminal | null = null;

		defaultFontSize = typeof termOptions.fontSize === 'number' ? termOptions.fontSize : 14;
		currentFontSize = defaultFontSize;

		void (async () => {
			try {
				const [{ Terminal }, { FitAddon }, { WebLinksAddon }] = await Promise.all([
					import('@xterm/xterm'),
					import('@xterm/addon-fit'),
					import('@xterm/addon-web-links')
				]);

				if (disposed || !terminalHost) return;

				instance = new Terminal(createTerminalOptions());
				const nextFitAddon = new FitAddon();
				const webLinksAddon = new WebLinksAddon((event, uri) => {
					event.preventDefault();
					window.open(uri, '_blank', 'noopener,noreferrer');
				});

				instance.loadAddon(nextFitAddon);
				instance.loadAddon(webLinksAddon);
				installKeyboardShortcuts(instance);
				instance.open(terminalHost);
				instance.onData((data) => {
					sendMessage({ type: 'input', data });
				});
				instance.onResize(({ cols, rows }) => {
					sendMessage({ type: 'resize', cols, rows });
				});

				terminal = instance;
				fitAddon = nextFitAddon;
				mounted = true;

				resizeObserver = new ResizeObserver(() => {
					requestFit();
				});
				resizeObserver.observe(terminalHost);

				await tick();
				requestFit();
			} catch (error) {
				console.error('Failed to initialize terminal emulator', error);
				setSocketState('error');
			}
		})();

		return () => {
			disposed = true;
			mounted = false;
			clearReconnectTimer();
			cancelAnimationFrame(fitFrame);
			resizeObserver?.disconnect();
			resizeObserver = null;
			disconnect(true);
			instance?.dispose();
			terminal = null;
			fitAddon = null;
		};
	});

	$effect(() => {
		if (!mounted) return;

		if (!connectOnMount) {
			disconnect(true);
			return;
		}

		if (!wsUrl || wsUrl === lastConnectedUrl) return;
		connect();
	});
</script>

<section
	class="terminal-shell flex h-full min-h-[32rem] flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950/90 shadow-2xl shadow-slate-950/30"
>
	<header
		class="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3"
	>
		<div class="min-w-0">
			<div class="flex flex-wrap items-center gap-3">
				<h2 class="text-sm font-semibold tracking-wide text-slate-100">{title}</h2>
				<span
					class={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-medium tracking-[0.18em] uppercase ${statusClasses[socketState]}`}
				>
					{socketState}
				</span>
			</div>
			<p class="mt-1 truncate text-xs text-slate-400">
				{lastConnectedUrl || wsUrl || 'No websocket configured'}
			</p>
		</div>

		<div class="flex flex-wrap items-center gap-2 text-xs font-medium text-slate-200">
			<button
				type="button"
				class="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 transition hover:bg-white/10"
				onclick={focusTerminal}
			>
				Focus
			</button>
			<button
				type="button"
				class="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 transition hover:bg-white/10"
				onclick={clearTerminal}
			>
				Clear
			</button>
			{#if socketState === 'open' || socketState === 'connecting'}
				<button
					type="button"
					class="rounded-full border border-rose-400/30 bg-rose-400/10 px-3 py-1.5 text-rose-100 transition hover:bg-rose-400/20"
					onclick={() => disconnect(true)}
				>
					Disconnect
				</button>
			{:else}
				<button
					type="button"
					class="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1.5 text-emerald-100 transition hover:bg-emerald-400/20"
					onclick={connect}
				>
					Connect
				</button>
			{/if}
		</div>
	</header>

	<div class="min-h-0 flex-1 overflow-hidden bg-slate-950 p-3">
		<div
			class="terminal-host h-full min-h-0"
			bind:this={terminalHost}
			onclick={focusTerminal}
			onkeydown={handleTerminalHostKeydown}
			role="button"
			tabindex="0"
			aria-label="Terminal viewport"
		></div>
	</div>

	<footer
		class="flex shrink-0 flex-wrap gap-2 border-t border-white/10 bg-slate-950/70 px-4 py-3 text-[11px] text-slate-400"
	>
		{#each shortcutHints as shortcut (shortcut)}
			<span class="rounded-full border border-white/10 bg-white/5 px-2 py-1">{shortcut}</span>
		{/each}
	</footer>
</section>

<style>
	.terminal-host {
		height: 100%;
		contain: strict;
	}

	.terminal-host :global(.xterm) {
		height: 100%;
	}

	.terminal-host :global(.xterm-viewport) {
		overflow-y: auto;
		scrollbar-width: thin;
		scrollbar-color: rgba(148, 163, 184, 0.45) transparent;
	}

	.terminal-host :global(.xterm-viewport::-webkit-scrollbar) {
		width: 10px;
	}

	.terminal-host :global(.xterm-viewport::-webkit-scrollbar-thumb) {
		border: 2px solid transparent;
		border-radius: 9999px;
		background: rgba(148, 163, 184, 0.35);
		background-clip: padding-box;
	}

	.terminal-host :global(.xterm-screen canvas) {
		image-rendering: auto;
	}
</style>
