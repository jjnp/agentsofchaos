<script module lang="ts">
	import { defineMeta } from '@storybook/addon-svelte-csf';

	import Dropdown from './Dropdown.svelte';
	import { sampleOptions } from './fixtures';

	const { Story } = defineMeta({
		title: 'Primitives/Dropdown',
		component: Dropdown,
		tags: ['autodocs'],
		args: {
			label: 'Target branch',
			placeholder: 'Choose a branch',
			options: sampleOptions,
			value: ''
		},
		argTypes: {
			inputSize: { control: 'select', options: ['sm', 'md', 'lg'] },
			tone: { control: 'select', options: ['primary', 'secondary', 'success', 'danger'] }
		}
	});
</script>

<Story name="Primary" />
<Story name="Selected" args={{ value: 'beta' }} />
<Story name="Danger" args={{ error: 'Please choose a valid target branch.' }} />
