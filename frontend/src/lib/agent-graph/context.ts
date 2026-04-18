import { getContext, setContext } from 'svelte';

import type { AgentGraphState } from './state.svelte';

const agentGraphContextKey = Symbol('agent-graph-state');

export const setAgentGraphContext = (getState: () => AgentGraphState) =>
	setContext(agentGraphContextKey, getState);

export const getAgentGraphContext = () => {
	const getState = getContext<(() => AgentGraphState) | undefined>(agentGraphContextKey);

	if (!getState) {
		throw new Error('Agent graph context is not available.');
	}

	return getState();
};
