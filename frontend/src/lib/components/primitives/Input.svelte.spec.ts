import { render } from 'vitest-browser-svelte';
import { describe, expect, it } from 'vitest';

import Input from './Input.svelte';

describe('Input', () => {
	it('renders label, hint, and error state', async () => {
		const screen = await render(Input, {
			label: 'Prompt title',
			hint: 'Keep it short.',
			error: 'Required field.',
			value: ''
		});

		await expect.element(screen.getByText('Prompt title')).toBeVisible();
		await expect.element(screen.getByText('Keep it short.')).toBeVisible();
		await expect.element(screen.getByText('Required field.')).toBeVisible();
		await expect.element(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true');
	});
});
