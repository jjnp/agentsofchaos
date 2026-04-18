<script lang="ts">
	import type { HTMLInputAttributes } from 'svelte/elements';

	import { getControlClasses } from './styles';
	import type { ControlSize, ControlTone } from './types';

	type InputProps = Omit<HTMLInputAttributes, 'size'> & {
		label?: string;
		hint?: string;
		error?: string;
		tone?: ControlTone;
		inputSize?: ControlSize;
		value?: string;
	};

	let nextInputId = 0;

	const createInputId = () => `input-${++nextInputId}`;

	let {
		label,
		hint,
		error,
		tone,
		inputSize = 'md',
		value = $bindable(''),
		id = createInputId(),
		class: className = '',
		type = 'text',
		...restProps
	}: InputProps = $props();

	const effectiveTone = $derived(tone ?? (error ? 'danger' : 'primary'));
	const describedBy = $derived(
		[hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') ||
			undefined
	);
	const classes = $derived(
		`${getControlClasses({ tone: effectiveTone, size: inputSize })}${className ? ` ${className}` : ''}`
	);
</script>

<label class="flex w-full flex-col gap-2">
	{#if label}
		<span class="text-sm font-medium text-text">{label}</span>
	{/if}

	<input
		{...restProps}
		{id}
		{type}
		bind:value
		class={classes}
		aria-invalid={error ? 'true' : undefined}
		aria-describedby={describedBy}
		data-tone={effectiveTone}
	/>

	{#if hint}
		<span id={`${id}-hint`} class="text-xs leading-5 text-text-muted">{hint}</span>
	{/if}

	{#if error}
		<span id={`${id}-error`} class="text-xs leading-5 font-medium text-danger">{error}</span>
	{/if}
</label>
