<script lang="ts">
	import type { HTMLTextareaAttributes } from 'svelte/elements';

	import { getControlClasses } from './styles';
	import type { ControlSize, ControlTone } from './types';

	type TextareaProps = HTMLTextareaAttributes & {
		label?: string;
		hint?: string;
		error?: string;
		tone?: ControlTone;
		inputSize?: ControlSize;
		value?: string;
	};

	let nextTextareaId = 0;
	const createTextareaId = () => `textarea-${++nextTextareaId}`;

	let {
		label,
		hint,
		error,
		tone,
		inputSize = 'md',
		value = $bindable(''),
		id = createTextareaId(),
		class: className = '',
		rows = 4,
		...restProps
	}: TextareaProps = $props();

	const effectiveTone = $derived(tone ?? (error ? 'danger' : 'primary'));
	const describedBy = $derived(
		[hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') ||
			undefined
	);
	const classes = $derived(
		`${getControlClasses({ tone: effectiveTone, size: inputSize })} resize-y${className ? ` ${className}` : ''}`
	);
</script>

<label class="flex w-full flex-col gap-2">
	{#if label}
		<span class="text-sm font-medium text-text">{label}</span>
	{/if}

	<textarea
		{...restProps}
		{id}
		{rows}
		bind:value
		class={classes}
		aria-invalid={error ? 'true' : undefined}
		aria-describedby={describedBy}
		data-tone={effectiveTone}
	></textarea>

	{#if hint}
		<span id={`${id}-hint`} class="text-xs leading-5 text-text-muted">{hint}</span>
	{/if}

	{#if error}
		<span id={`${id}-error`} class="text-xs leading-5 font-medium text-danger">{error}</span>
	{/if}
</label>
