import { render } from 'vitest-browser-svelte';
import { describe, expect, it, vi } from 'vitest';

import Button from './Button.svelte';

describe('Button', () => {
	it('renders the provided label and handles clicks', async () => {
		const handleClick = vi.fn();
		const screen = await render(Button, { label: 'Run merge', onclick: handleClick });

		const button = screen.getByRole('button', { name: 'Run merge' });
		await button.click();

		await expect.element(button).toHaveAttribute('data-variant', 'primary');
		expect(handleClick).toHaveBeenCalledTimes(1);
	});
});
