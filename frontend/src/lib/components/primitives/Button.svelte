<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';

	import { getButtonClasses } from './styles';
	import type { ButtonVariant, ControlSize } from './types';

	type ButtonProps = HTMLButtonAttributes & {
		children?: Snippet;
		label?: string;
		variant?: ButtonVariant;
		size?: ControlSize;
		fullWidth?: boolean;
		loading?: boolean;
	};

	let {
		children,
		label,
		variant = 'primary',
		size = 'md',
		fullWidth = false,
		loading = false,
		class: className = '',
		type = 'button',
		disabled = false,
		...restProps
	}: ButtonProps = $props();

	const classes = $derived(
		`${getButtonClasses({ variant, size, fullWidth })}${className ? ` ${className}` : ''}`
	);
</script>

<button {...restProps} {type} class={classes} disabled={disabled || loading} data-variant={variant}>
	{#if loading}
		<span
			class="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent"
		></span>
	{/if}
	{#if children}
		{@render children()}
	{:else}
		{label}
	{/if}
</button>
