<script lang="ts">
	import { TerminalStream } from '$lib';

	type SocketState = 'idle' | 'connecting' | 'open' | 'closed' | 'error';

	let wsUrl = $state('ws://127.0.0.1:8787/terminal');
	let status = $state<SocketState>('idle');
	let reconnect = $state(true);

	const resizeSnippet = '{"type":"resize","cols":120,"rows":34}';
	const backendSnippet = 'npm run terminal:test-server';
	const usageSnippet = [
		'<script lang="ts">',
		"  import { TerminalStream } from '$lib';",
		'</scr' + 'ipt>',
		'',
		'<TerminalStream',
		'  wsUrl="ws://127.0.0.1:8787/terminal"',
		'  title="Agent shell"',
		'/>'
	].join('\n');
</script>

<svelte:head>
	<title>Terminal stream demo</title>
</svelte:head>

<div
	class="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-8 text-slate-100 md:px-6 lg:px-8"
>
	<section class="grid gap-6 lg:grid-cols-[22rem,1fr]">
		<aside
			class="space-y-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30 backdrop-blur"
		>
			<div>
				<p class="text-xs font-semibold tracking-[0.24em] text-sky-300 uppercase">
					Websocket terminal
				</p>
				<h1 class="mt-2 text-2xl font-semibold text-white">
					Ghostty-style terminal stream for Svelte
				</h1>
				<p class="mt-3 text-sm leading-6 text-slate-300">
					This component uses xterm.js under the hood so ANSI escape sequences, cursor movement,
					colors, alternate screens and full keyboard input all behave like a real PTY-backed
					terminal.
				</p>
			</div>

			<label class="block space-y-2">
				<span class="text-xs font-semibold tracking-[0.18em] text-slate-400 uppercase"
					>Websocket URL</span
				>
				<input
					bind:value={wsUrl}
					class="w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-2 font-mono text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-400/50 focus:ring-0"
					placeholder="ws://127.0.0.1:8787/terminal"
				/>
			</label>

			<label
				class="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
			>
				<input
					bind:checked={reconnect}
					class="rounded border-white/20 bg-slate-900"
					type="checkbox"
				/>
				<span>Reconnect</span>
			</label>

			<div class="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
				<p class="text-xs font-semibold tracking-[0.18em] text-slate-400 uppercase">
					Quick test backend
				</p>
				<p class="mt-2 text-sm leading-6 text-slate-400">
					Run the bundled PTY websocket server in a second terminal, then connect this page to
					<code class="rounded bg-white/10 px-1.5 py-0.5 text-xs text-slate-200"
						>ws://127.0.0.1:8787/terminal</code
					>.
				</p>
				<pre
					class="mt-3 overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-3 text-xs text-emerald-200">{backendSnippet}</pre>
			</div>

			<div class="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
				<p class="text-xs font-semibold tracking-[0.18em] text-slate-400 uppercase">
					Current status
				</p>
				<p class="mt-2 text-sm font-medium text-white">{status}</p>
				<p class="mt-2 text-sm leading-6 text-slate-400">
					Incoming websocket frames can be plain strings or binary UTF-8/ANSI data. Outgoing typing
					is sent as raw terminal input. Resize events default to JSON:
				</p>
				<pre
					class="mt-3 overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-3 text-xs text-sky-200">{resizeSnippet}</pre>
			</div>

			<div class="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
				<p class="text-xs font-semibold tracking-[0.18em] text-slate-400 uppercase">Usage</p>
				<pre
					class="mt-3 overflow-x-auto rounded-xl border border-white/10 bg-black/30 p-3 text-xs text-slate-200">{usageSnippet}</pre>
			</div>
		</aside>

		<div class="min-h-[42rem]">
			<TerminalStream
				{wsUrl}
				{reconnect}
				title="Agent shell"
				onStatusChange={(next) => (status = next)}
			/>
		</div>
	</section>
</div>
