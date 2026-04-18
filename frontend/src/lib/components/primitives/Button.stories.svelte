<script module lang="ts">
	import { defineMeta } from '@storybook/addon-svelte-csf';

	import Button from './Button.svelte';

	const { Story } = defineMeta({
		title: 'Primitives/Button',
		component: Button,
		tags: ['autodocs'],
		args: {
			label: 'Launch branch'
		},
		argTypes: {
			variant: {
				control: 'select',
				options: ['primary', 'secondary', 'success', 'danger', 'ghost']
			},
			size: { control: 'select', options: ['sm', 'md', 'lg'] }
		}
	});
</script>

<Story name="Primary" args={{ variant: 'primary' }} />
<Story name="Danger" args={{ variant: 'danger', label: 'Delete branch' }} />
<Story name="Ghost" args={{ variant: 'ghost', label: 'Inspect details' }} />
<Story name="Loading" args={{ loading: true, label: 'Syncing' }} />
<Story name="Full width" args={{ fullWidth: true, label: 'Run for all workers' }} />
