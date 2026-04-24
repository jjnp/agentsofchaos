import type { RequestHandler } from '@sveltejs/kit';

const DEFAULT_BACKEND = 'http://127.0.0.1:8000';

const HOP_BY_HOP_HEADERS = new Set([
	'host',
	'connection',
	'keep-alive',
	'transfer-encoding',
	'te',
	'trailer',
	'upgrade',
	'proxy-authorization',
	'proxy-authenticate',
	'content-length'
]);

function backendBaseUrl(): string {
	const value = process.env['ORCHESTRATOR_V2_BASE_URL'] ?? DEFAULT_BACKEND;
	return value.replace(/\/$/, '');
}

function buildTargetUrl(path: string, search: string): string {
	const normalized = path.startsWith('/') ? path : `/${path}`;
	return `${backendBaseUrl()}${normalized}${search}`;
}

function filteredHeaders(source: Headers): Headers {
	const out = new Headers();
	for (const [name, value] of source) {
		if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase())) {
			out.set(name, value);
		}
	}
	return out;
}

async function proxy(request: Request, path: string, search: string): Promise<Response> {
	const target = buildTargetUrl(path, search);
	const init: RequestInit = {
		method: request.method,
		headers: filteredHeaders(request.headers),
		redirect: 'manual'
	};
	if (request.method !== 'GET' && request.method !== 'HEAD') {
		init.body = await request.arrayBuffer();
	}

	let upstream: Response;
	try {
		upstream = await fetch(target, init);
	} catch (error) {
		return new Response(
			JSON.stringify({
				detail: `orchestrator-v2 unreachable at ${backendBaseUrl()}`,
				error: String(error)
			}),
			{ status: 502, headers: { 'content-type': 'application/json' } }
		);
	}

	const responseHeaders = filteredHeaders(upstream.headers);
	// SSE streams must not be buffered; node fetch already exposes a streaming body.
	return new Response(upstream.body, {
		status: upstream.status,
		statusText: upstream.statusText,
		headers: responseHeaders
	});
}

const handler: RequestHandler = ({ request, params, url }) => {
	const path = params['path'] ?? '';
	return proxy(request, `/${path}`, url.search);
};

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
