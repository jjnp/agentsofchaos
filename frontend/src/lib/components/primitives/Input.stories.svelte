<script module lang="ts">
	import { defineMeta } from '@storybook/addon-svelte-csf';

	import Input from './Input.svelte';

	const { Story } = defineMeta({
		title: 'Primitives/Input',
		component: Input,
		tags: ['autodocs'],
		args: {
			label: 'Prompt title',
			placeholder: 'Summarize the merge conflict',
			hint: 'Use a short action-oriented name.',
			value: ''
		},
		argTypes: {
			inputSize: { control: 'select', options: ['sm', 'md', 'lg'] },
			tone: { control: 'select', options: ['primary', 'secondary', 'success', 'danger'] }
		}
	});
</script>

<Story name="Primary" />
<Story name="Success" args={{ tone: 'success', value: 'Ready to merge' }} />
<Story name="Danger" args={{ error: 'A title is required to continue.' }} />
