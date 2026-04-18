import { getContext, setContext } from 'svelte';

import type { AgentGraphState } from './state.svelte';

const agentGraphContextKey = Symbol('agent-graph-state');

export const setAgentGraphContext = (state: AgentGraphState) =>
	setContext(agentGraphContextKey, state);

export const getAgentGraphContext = () => {
	const state = getContext<AgentGraphState | undefined>(agentGraphContextKey);

	if (!state) {
		throw new Error('Agent graph context is not available.');
	}

	return state;
};
