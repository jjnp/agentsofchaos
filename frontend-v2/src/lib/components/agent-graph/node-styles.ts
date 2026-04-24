import type { NodeKind, NodeStatus } from '$lib/orchestrator/contracts';

export const NODE_RADIUS = 28;
export const NODE_DIAMETER = NODE_RADIUS * 2;

export function nodeKindColorVar(kind: NodeKind): string {
	switch (kind) {
		case 'root':
			return 'var(--color-kind-root)';
		case 'prompt':
			return 'var(--color-kind-prompt)';
		case 'fork':
			return 'var(--color-kind-fork)';
		case 'merge':
			return 'var(--color-kind-merge)';
		case 'import':
			return 'var(--color-kind-import)';
		case 'manual':
			return 'var(--color-kind-manual)';
	}
}

export function nodeStatusColorVar(status: NodeStatus): string {
	switch (status) {
		case 'ready':
			return 'var(--color-status-ready)';
		case 'running':
			return 'var(--color-status-running)';
		case 'failed':
			return 'var(--color-status-failed)';
		case 'cancelled':
			return 'var(--color-status-cancelled)';
		case 'code_conflicted':
			return 'var(--color-status-code-conflicted)';
		case 'context_conflicted':
			return 'var(--color-status-context-conflicted)';
		case 'both_conflicted':
			return 'var(--color-status-both-conflicted)';
	}
}

export function nodeKindLabel(kind: NodeKind): string {
	return kind.replace(/_/g, ' ');
}

export function nodeStatusLabel(status: NodeStatus): string {
	return status.replace(/_/g, ' ');
}
