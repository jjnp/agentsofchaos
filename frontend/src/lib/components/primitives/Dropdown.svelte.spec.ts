import { render } from 'vitest-browser-svelte';
import { describe, expect, it } from 'vitest';

import Dropdown from './Dropdown.svelte';
import { sampleOptions } from './fixtures';

describe('Dropdown', () => {
	it('renders options and supports selecting a value', async () => {
		const screen = await render(Dropdown, {
			label: 'Target branch',
			options: sampleOptions,
			value: ''
		});

		const select = screen.getByRole('combobox');
		await select.selectOptions('beta');

		await expect.element(select).toHaveValue('beta');
		await expect
			.element(screen.getByRole('option', { name: 'Delta' }))
			.toHaveAttribute('disabled', '');
	});
});
