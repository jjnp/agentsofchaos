import { describe, expect, it } from 'vitest';

import { filterAutocompleteOptions, getNextActiveIndex } from './autocomplete';
import { sampleOptions } from './fixtures';

describe('autocomplete helpers', () => {
	it('filters options by label, value, and description while excluding disabled entries', () => {
		const results = filterAutocompleteOptions(sampleOptions, 'validation');

		expect(results).toEqual([expect.objectContaining({ label: 'Gamma', value: 'gamma' })]);
		expect(filterAutocompleteOptions(sampleOptions, 'merge')).toEqual([]);
	});

	it('wraps keyboard navigation through the filtered option list', () => {
		expect(getNextActiveIndex({ currentIndex: -1, direction: 1, optionCount: 3 })).toBe(0);
		expect(getNextActiveIndex({ currentIndex: 0, direction: -1, optionCount: 3 })).toBe(2);
		expect(getNextActiveIndex({ currentIndex: 2, direction: 1, optionCount: 3 })).toBe(0);
	});
});
