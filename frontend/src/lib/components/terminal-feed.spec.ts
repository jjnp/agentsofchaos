import { describe, expect, it } from 'vitest';

import { getTerminalFeedUpdate } from './terminal-feed';

describe('getTerminalFeedUpdate', () => {
	it('returns no work when the terminal buffer is unchanged', () => {
		expect(getTerminalFeedUpdate('hello', 'hello')).toEqual({ mode: 'none', text: '' });
	});

	it('appends only the delta for growing buffers', () => {
		expect(getTerminalFeedUpdate('hello', 'hello world')).toEqual({
			mode: 'append',
			text: ' world'
		});
	});

	it('replaces the entire buffer when the content diverges', () => {
		expect(getTerminalFeedUpdate('hello world', 'goodbye')).toEqual({
			mode: 'replace',
			text: 'goodbye'
		});
	});
});
