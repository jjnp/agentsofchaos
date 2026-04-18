import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

const DEFAULT_ORCHESTRATOR_BASE_URL = 'http://127.0.0.1:3000';

const getOrchestratorBaseUrl = () => env.ORCHESTRATOR_BASE_URL || DEFAULT_ORCHESTRATOR_BASE_URL;

const getTargetUrl = (pathParam: string | undefined, url: URL) => {
	const targetUrl = new URL(getOrchestratorBaseUrl());
	targetUrl.pathname = `/api/${pathParam ?? ''}`;
	targetUrl.search = url.search;
	return targetUrl;
};

const forwardRequest: RequestHandler = async ({ params, request, url }) => {
	const targetUrl = getTargetUrl(params.path, url);
	const headers = new Headers(request.headers);
	headers.delete('host');
	headers.delete('connection');
	headers.delete('content-length');

	const body =
		request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.text();

	const response = await fetch(targetUrl, {
		method: request.method,
		headers,
		body
	});

	const responseHeaders = new Headers(response.headers);
	responseHeaders.delete('content-length');
	responseHeaders.delete('connection');

	return new Response(response.body, {
		status: response.status,
		statusText: response.statusText,
		headers: responseHeaders
	});
};

export const GET = forwardRequest;
export const POST = forwardRequest;
