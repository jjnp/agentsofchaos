import { describe, expect, it } from 'vitest';

import { getButtonClasses, getControlClasses } from './styles';

describe('primitive styles', () => {
	it('builds button classes for variants and sizing', () => {
		const classes = getButtonClasses({ variant: 'danger', size: 'lg', fullWidth: true });

		expect(classes).toContain('bg-danger');
		expect(classes).toContain('min-h-12');
		expect(classes).toContain('w-full');
	});

	it('builds control classes for semantic tones', () => {
		const classes = getControlClasses({ tone: 'success', size: 'sm' });

		expect(classes).toContain('border-success/50');
		expect(classes).toContain('min-h-10');
	});
});
