import { render } from 'vitest-browser-svelte';
import { describe, expect, it } from 'vitest';

import Dropdown from './Dropdown.svelte';
import { sampleOptions } from './fixtures';

describe('Dropdown', () => {
	it('renders a custom listbox and supports selecting a value', async () => {
		const screen = await render(Dropdown, {
			label: 'Target branch',
			options: sampleOptions,
			value: ''
		});

		const combobox = screen.getByRole('combobox');
		await combobox.click();
		await expect
			.element(screen.getByRole('option', { name: 'Delta Merge candidate' }))
			.toHaveAttribute('aria-disabled', 'true');
		await screen.getByRole('option', { name: 'Beta Secondary reasoning branch' }).click();

		await expect.element(combobox).toHaveTextContent('Beta');
		await expect.element(combobox).toHaveAttribute('aria-expanded', 'false');
	});
});
