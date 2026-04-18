import * as v from 'valibot';

import { createAgentNode, type AgentNode } from './types';

export const forkPromptSchema = v.pipe(v.string(), v.trim(), v.minLength(1));

export type ForkPrompt = string;

const getForkNodeName = (prompt: ForkPrompt) => {
	const normalizedPrompt = prompt.trim().replace(/\s+/g, ' ');
	return normalizedPrompt.length <= 28
		? normalizedPrompt
		: `${normalizedPrompt.slice(0, 25).trimEnd()}…`;
};

export const merge = (baseNode: AgentNode, incomingNode: AgentNode): AgentNode => {
	void baseNode;
	return incomingNode;
};

export const fork = (node: AgentNode, prompt: ForkPrompt): AgentNode => {
	const validatedPrompt = v.parse(forkPromptSchema, prompt);

	return createAgentNode({
		name: getForkNodeName(validatedPrompt),
		parentId: node.id,
		status: 'running',
		details: {
			contextUsage: {
				tokens: 0,
				percentage: 0
			}
		}
	});
};
