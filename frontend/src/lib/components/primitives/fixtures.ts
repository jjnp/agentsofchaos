import type { ControlOption } from './types';

export const sampleOptions: readonly ControlOption[] = [
	{ label: 'Alpha', value: 'alpha', description: 'Primary exploration path' },
	{ label: 'Beta', value: 'beta', description: 'Secondary reasoning branch' },
	{ label: 'Gamma', value: 'gamma', description: 'Validation workspace' },
	{ label: 'Delta', value: 'delta', description: 'Merge candidate', disabled: true }
];
