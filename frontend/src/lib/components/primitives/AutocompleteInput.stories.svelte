<script module lang="ts">
	import { defineMeta } from '@storybook/addon-svelte-csf';

	import AutocompleteInput from './AutocompleteInput.svelte';
	import { sampleOptions } from './fixtures';

	const { Story } = defineMeta({
		title: 'Primitives/Autocomplete Input',
		component: AutocompleteInput,
		tags: ['autodocs'],
		args: {
			label: 'Search workspace',
			placeholder: 'Filter by branch or purpose',
			hint: 'Try “merge” or “validation”.',
			options: sampleOptions,
			value: ''
		},
		argTypes: {
			inputSize: { control: 'select', options: ['sm', 'md', 'lg'] },
			tone: { control: 'select', options: ['primary', 'secondary', 'success', 'danger'] }
		}
	});
</script>

<Story name="Default" />
<Story name="Filtered" args={{ value: 'ga' }} />
<Story name="Danger" args={{ error: 'Please select an existing workspace.' }} />
