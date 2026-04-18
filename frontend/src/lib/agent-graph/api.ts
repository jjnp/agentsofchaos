import * as v from 'valibot';

import type { AgentNode } from './types';

export const forkPromptSchema = v.pipe(v.string(), v.trim(), v.minLength(1));

export type ForkPrompt = string;

export const merge = (baseNode: AgentNode, incomingNode: AgentNode): AgentNode => {
	void baseNode;
	return incomingNode;
};

export const fork = (node: AgentNode, prompt: ForkPrompt): AgentNode => {
	void prompt;
	return node;
};
