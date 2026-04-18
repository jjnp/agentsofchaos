import * as v from 'valibot';

import {
	apiErrorSchema,
	createInstanceResponseSchema,
	forkInstanceResponseSchema,
	forkPointArtifactSchema,
	mergeDetailsSchema,
	mergePrepResponseSchema,
	mergeResponseSchema,
	orchestratorInstanceSchema,
	orchestratorInstancesResponseSchema,
	orchestratorStateSchema,
	promptInstanceResponseSchema,
	stopInstanceResponseSchema,
	type ApiErrorResponse,
	type CreateInstanceResponse,
	type ForkInstanceResponse,
	type ForkPointArtifact,
	type MergeDetails,
	type MergePrepResponse,
	type MergeResponse,
	type OrchestratorInstance,
	type OrchestratorInstancesResponse,
	type OrchestratorState,
	type PromptInstanceResponse,
	type StopInstanceResponse
} from './types';

const DEFAULT_BASE_PATH = '/api/orchestrator';

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');
const trimLeadingSlash = (value: string) => value.replace(/^\/+/, '');

const joinUrl = (baseUrl: string, path: string) => {
	const normalizedBaseUrl = trimTrailingSlash(baseUrl);
	const normalizedPath = trimLeadingSlash(path);
	return `${normalizedBaseUrl}/${normalizedPath}`;
};

const buildJsonHeaders = (headers?: HeadersInit) => {
	const nextHeaders = new Headers(headers);
	if (!nextHeaders.has('accept')) {
		nextHeaders.set('accept', 'application/json');
	}
	return nextHeaders;
};

export class OrchestratorApiError extends Error {
	readonly status: number;
	readonly code: string;

	constructor(response: Response, error: ApiErrorResponse['error']) {
		super(error.message);
		this.name = 'OrchestratorApiError';
		this.status = response.status;
		this.code = error.code;
	}
}

export type OrchestratorFetch = typeof fetch;

export type OrchestratorClientOptions = Readonly<{
	baseUrl?: string;
	fetch?: OrchestratorFetch;
}>;

const parseErrorResponse = async (response: Response) => {
	try {
		const payload = await response.json();
		return v.parse(apiErrorSchema, payload).error;
	} catch {
		return {
			code: 'INTERNAL_ERROR',
			message: `Request failed with status ${response.status}`
		} satisfies ApiErrorResponse['error'];
	}
};

const requestJson = async <TSchema extends v.BaseSchema<unknown, unknown, v.BaseIssue<unknown>>>(
	fetchFn: OrchestratorFetch,
	url: string,
	schema: TSchema,
	init?: RequestInit
): Promise<v.InferOutput<TSchema>> => {
	const response = await fetchFn(url, {
		...init,
		headers: buildJsonHeaders(init?.headers)
	});

	if (!response.ok) {
		throw new OrchestratorApiError(response, await parseErrorResponse(response));
	}

	return v.parse(schema, await response.json());
};

const requestText = async (fetchFn: OrchestratorFetch, url: string, init?: RequestInit) => {
	const response = await fetchFn(url, init);
	if (!response.ok) {
		throw new OrchestratorApiError(response, await parseErrorResponse(response));
	}
	return response.text();
};

export type OrchestratorClient = ReturnType<typeof createOrchestratorClient>;

export const createOrchestratorClient = ({
	baseUrl = DEFAULT_BASE_PATH,
	fetch: fetchFn = fetch
}: OrchestratorClientOptions = {}) => {
	const resolvedBaseUrl = trimTrailingSlash(baseUrl);

	return {
		baseUrl: resolvedBaseUrl,
		getState: () =>
			requestJson(fetchFn, joinUrl(resolvedBaseUrl, 'state'), orchestratorStateSchema),
		listInstances: () =>
			requestJson(
				fetchFn,
				joinUrl(resolvedBaseUrl, 'instances'),
				orchestratorInstancesResponseSchema
			),
		getInstance: (slot: number) =>
			requestJson(
				fetchFn,
				joinUrl(resolvedBaseUrl, `instances/${slot}`),
				orchestratorInstanceSchema
			),
		createInstance: () =>
			requestJson(fetchFn, joinUrl(resolvedBaseUrl, 'instances'), createInstanceResponseSchema, {
				method: 'POST'
			}),
		promptInstance: (slot: number, message: string) =>
			requestJson(
				fetchFn,
				joinUrl(resolvedBaseUrl, `instances/${slot}/prompt`),
				promptInstanceResponseSchema,
				{
					method: 'POST',
					headers: {
						'content-type': 'application/json'
					},
					body: JSON.stringify({ message })
				}
			),
		forkInstance: (slot: number) =>
			requestJson(
				fetchFn,
				joinUrl(resolvedBaseUrl, `instances/${slot}/fork`),
				forkInstanceResponseSchema,
				{ method: 'POST' }
			),
		stopInstance: (slot: number) =>
			requestJson(
				fetchFn,
				joinUrl(resolvedBaseUrl, `instances/${slot}/stop`),
				stopInstanceResponseSchema,
				{ method: 'POST' }
			),
		prepareMerge: (sourceSlot: number, targetSlot: number) =>
			requestJson(fetchFn, joinUrl(resolvedBaseUrl, 'merge-prep'), mergePrepResponseSchema, {
				method: 'POST',
				headers: {
					'content-type': 'application/json'
				},
				body: JSON.stringify({ sourceSlot, targetSlot })
			}),
		merge: (sourceSlot: number, targetSlot: number) =>
			requestJson(fetchFn, joinUrl(resolvedBaseUrl, 'merge'), mergeResponseSchema, {
				method: 'POST',
				headers: {
					'content-type': 'application/json'
				},
				body: JSON.stringify({ sourceSlot, targetSlot })
			}),
		getForkPointArtifact: (slot: number) =>
			requestJson(
				fetchFn,
				joinUrl(resolvedBaseUrl, `instances/${slot}/artifacts/fork-point`),
				forkPointArtifactSchema
			),
		getMergeDetailsArtifact: (slot: number) =>
			requestJson(
				fetchFn,
				joinUrl(resolvedBaseUrl, `instances/${slot}/artifacts/merge-details`),
				mergeDetailsSchema
			),
		getMergeContextArtifact: (slot: number) =>
			requestText(fetchFn, joinUrl(resolvedBaseUrl, `instances/${slot}/artifacts/merge-context`))
	};
};

export type {
	ApiErrorResponse,
	CreateInstanceResponse,
	ForkInstanceResponse,
	ForkPointArtifact,
	MergeDetails,
	MergePrepResponse,
	MergeResponse,
	OrchestratorInstance,
	OrchestratorInstancesResponse,
	OrchestratorState,
	PromptInstanceResponse,
	StopInstanceResponse
};
