import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const defaultBaseUrl = 'http://127.0.0.1:3000';

function getBaseUrl() {
	return (env.ORCHESTRATOR_BASE_URL || defaultBaseUrl).replace(/\/$/, '');
}

function buildTargetUrl(requestUrl: URL, path: string[] | undefined) {
	const relativePath = path?.join('/') ?? '';
	const target = new URL(`${getBaseUrl()}/api/${relativePath}`);
	target.search = requestUrl.search;
	return target;
}

async function proxy(event: Parameters<RequestHandler>[0]) {
	const targetUrl = buildTargetUrl(event.url, event.params.path?.split('/').filter(Boolean));
	const request = event.request;
	const headers = new Headers(request.headers);
	headers.delete('host');
	headers.delete('connection');
	headers.delete('content-length');

	const body =
		request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.arrayBuffer();

	const upstream = await fetch(targetUrl, {
		method: request.method,
		headers,
		body
	});

	const responseHeaders = new Headers(upstream.headers);
	responseHeaders.delete('content-length');
	return new Response(upstream.body, {
		status: upstream.status,
		statusText: upstream.statusText,
		headers: responseHeaders
	});
}

export const GET: RequestHandler = proxy;
export const POST: RequestHandler = proxy;
