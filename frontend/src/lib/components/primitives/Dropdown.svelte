<script lang="ts">
	import type { HTMLSelectAttributes } from 'svelte/elements';

	import { getControlClasses } from './styles';
	import type { ControlOption, ControlSize, ControlTone } from './types';

	type DropdownProps = Omit<HTMLSelectAttributes, 'size'> & {
		label?: string;
		hint?: string;
		error?: string;
		tone?: ControlTone;
		inputSize?: ControlSize;
		placeholder?: string;
		options: readonly ControlOption[];
		value?: string;
	};

	let nextDropdownId = 0;

	const createDropdownId = () => `dropdown-${++nextDropdownId}`;

	let {
		label,
		hint,
		error,
		tone,
		inputSize = 'md',
		placeholder = 'Select an option',
		options,
		value = $bindable(''),
		id = createDropdownId(),
		class: className = '',
		...restProps
	}: DropdownProps = $props();

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

	<select
		{...restProps}
		{id}
		bind:value
		class={classes}
		aria-invalid={error ? 'true' : undefined}
		aria-describedby={describedBy}
		data-tone={effectiveTone}
	>
		<option value="" disabled>{placeholder}</option>
		{#each options as option (option.value)}
			<option value={option.value} disabled={option.disabled}>{option.label}</option>
		{/each}
	</select>

	{#if hint}
		<span id={`${id}-hint`} class="text-xs leading-5 text-text-muted">{hint}</span>
	{/if}

	{#if error}
		<span id={`${id}-error`} class="text-xs leading-5 font-medium text-danger">{error}</span>
	{/if}
</label>
