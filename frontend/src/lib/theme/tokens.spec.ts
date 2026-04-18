import { describe, expect, it } from 'vitest';

import { themeColors, themeRadii } from './tokens';

describe('theme tokens', () => {
	it('exposes the expected semantic color tokens', () => {
		expect(themeColors).toMatchObject({
			canvas: '#0c0d0a',
			surface: '#12130f',
			text: '#d6d3b8',
			primary: '#e8d548'
		});
	});

	it('keeps reusable radius tokens available', () => {
		expect(themeRadii.panel).toBe('1.5rem');
		expect(themeRadii.pill).toBe('999px');
	});
});
