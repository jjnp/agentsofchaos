import { createHash } from 'node:crypto';

import { env } from '$env/dynamic/private';

import type { FileDiff } from '$lib/features/node-diff/schemas';

interface SummaryResult {
	summary: string;
	cached: boolean;
}

function truncate(value: string, maxLength: number) {
	return value.length <= maxLength ? value : `${value.slice(0, maxLength - 1)}…`;
}

function compactDiffSnippet(file: FileDiff, maxLines = 18) {
	const lines = file.hunks.flatMap((hunk) => [
		hunk.header,
		...hunk.lines.map(
			(line) => `${line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' '}${line.content}`
		)
	]);

	return truncate(lines.slice(0, maxLines).join('\n'), 1_800);
}

function compactContext(context: string | undefined, files: FileDiff[]) {
	const fileDigest = files
		.slice(0, 8)
		.map((file) => `${file.path} (+${file.additions}/-${file.deletions}, ${file.changeType})`)
		.join('\n');

	const userContext = context ? `Additional compact context:\n${truncate(context, 1_200)}\n\n` : '';

	return `${userContext}Changed files:\n${fileDigest}`;
}

function cacheKey(value: unknown) {
	return createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

const summaryCache = new Map<string, Pick<SummaryResult, 'summary'>>();

function getCachedSummary(key: string) {
	const cached = summaryCache.get(key);
	return cached ? { ...cached, cached: true } : null;
}

function setCachedSummary(key: string, value: Pick<SummaryResult, 'summary'>) {
	summaryCache.set(key, value);
	return { ...value, cached: false } satisfies SummaryResult;
}

export function buildOverallSummaryPrompt(input: {
	prompt: string;
	files: FileDiff[];
	context?: string;
}) {
	const spotlight = input.files.slice(0, 3);

	return [
		'You summarize a coding-agent graph node for a human reviewing the branch history.',
		'Return 2-4 concise sentences. Focus on intent, the most important file changes, and likely product impact.',
		`Node prompt:\n${truncate(input.prompt, 1_500)}`,
		compactContext(input.context, input.files),
		'Key diff excerpts:',
		...spotlight.map((file) => `\n# ${file.path}\n${compactDiffSnippet(file, 14)}`)
	].join('\n\n');
}

export function buildFileSummaryPrompt(input: {
	prompt: string;
	file: FileDiff;
	context?: string;
}) {
	return [
		'You summarize a single changed file from a coding-agent graph node.',
		'Return 1-3 sentences describing what changed, why it likely changed, and any notable risks or follow-up questions.',
		`Node prompt:\n${truncate(input.prompt, 1_200)}`,
		input.context ? `Additional compact context:\n${truncate(input.context, 800)}` : '',
		`File: ${input.file.path} (${input.file.changeType}, +${input.file.additions}/-${input.file.deletions})`,
		`Unified diff excerpt:\n${compactDiffSnippet(input.file)}`
	]
		.filter(Boolean)
		.join('\n\n');
}

function heuristicSummaryForFile(file: FileDiff, prompt: string) {
	const actions: string[] = [];
	if (file.additions > 0)
		actions.push(`adds ${file.additions} line${file.additions === 1 ? '' : 's'}`);
	if (file.deletions > 0)
		actions.push(`removes ${file.deletions} line${file.deletions === 1 ? '' : 's'}`);
	const actionSummary =
		actions.length > 0 ? actions.join(' and ') : 'touches the file without line-level changes';

	return `${file.path} was ${file.changeType} and ${actionSummary}. It appears to support the node goal: ${truncate(prompt, 140)}`;
}

function heuristicOverallSummary(files: FileDiff[], prompt: string) {
	if (files.length === 0) {
		return `No file-level diff was detected for this node. Intended task: ${truncate(prompt, 180)}`;
	}

	const topFiles = [...files]
		.sort((left, right) => right.additions + right.deletions - (left.additions + left.deletions))
		.slice(0, 3)
		.map((file) => file.path)
		.join(', ');

	const additions = files.reduce((total, file) => total + file.additions, 0);
	const deletions = files.reduce((total, file) => total + file.deletions, 0);

	return `This node changes ${files.length} file${files.length === 1 ? '' : 's'} (${topFiles}) with +${additions}/-${deletions} total lines. The changes appear aimed at: ${truncate(prompt, 180)}`;
}

async function generateWithOpenAI(prompt: string) {
	const apiKey = env.OPENAI_API_KEY;
	if (!apiKey) return null;

	const baseUrl = env.OPENAI_BASE_URL ?? 'https://api.openai.com/v1';
	const model = env.OPENAI_MODEL ?? 'gpt-4.1-mini';
	const response = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
		method: 'POST',
		headers: {
			'content-type': 'application/json',
			authorization: `Bearer ${apiKey}`
		},
		body: JSON.stringify({
			model,
			temperature: 0.2,
			messages: [{ role: 'user', content: prompt }]
		})
	});

	if (!response.ok) {
		throw new Error(`OpenAI summary request failed with status ${response.status}`);
	}

	const data = (await response.json()) as {
		choices?: Array<{ message?: { content?: string | null } }>;
	};

	return data.choices?.[0]?.message?.content?.trim() || null;
}

async function generateSummary(input: {
	kind: 'overview' | 'file';
	cacheParts: unknown;
	prompt: string;
	fallbackSummary: string;
}): Promise<SummaryResult> {
	const key = cacheKey({ kind: input.kind, value: input.cacheParts });
	const cached = getCachedSummary(key);
	if (cached) return cached;

	const generated = await generateWithOpenAI(input.prompt);
	if (generated) {
		return setCachedSummary(key, {
			summary: generated
		});
	}

	return setCachedSummary(key, {
		summary: input.fallbackSummary
	});
}

export async function summarizeNodeOverview(input: {
	prompt: string;
	files: FileDiff[];
	context?: string;
}) {
	const prompt = buildOverallSummaryPrompt(input);
	return generateSummary({
		kind: 'overview',
		cacheParts: input,
		prompt,
		fallbackSummary: heuristicOverallSummary(input.files, input.prompt)
	});
}

export async function summarizeNodeFile(input: {
	prompt: string;
	file: FileDiff;
	context?: string;
}) {
	const prompt = buildFileSummaryPrompt(input);
	return generateSummary({
		kind: 'file',
		cacheParts: input,
		prompt,
		fallbackSummary: heuristicSummaryForFile(input.file, input.prompt)
	});
}

export function clearNodeDiffSummaryCache() {
	summaryCache.clear();
}
