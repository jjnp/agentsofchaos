<script lang="ts">
	import type { HTMLInputAttributes } from 'svelte/elements';

	import { filterAutocompleteOptions, getNextActiveIndex } from './autocomplete';
	import { getControlClasses } from './styles';
	import type { ControlOption, ControlSize, ControlTone } from './types';

	type AutocompleteInputProps = Omit<HTMLInputAttributes, 'size' | 'value'> & {
		label?: string;
		hint?: string;
		error?: string;
		tone?: ControlTone;
		inputSize?: ControlSize;
		placeholder?: string;
		options: readonly ControlOption[];
		value?: string;
		selectedValue?: string | null;
		maxVisibleResults?: number;
		noResultsMessage?: string;
		onSelect?: (option: ControlOption) => void;
	};

	let nextAutocompleteId = 0;

	const createAutocompleteId = () => `autocomplete-${++nextAutocompleteId}`;

	let {
		label,
		hint,
		error,
		tone,
		inputSize = 'md',
		placeholder = 'Search…',
		options,
		value = $bindable(''),
		selectedValue = $bindable<string | null>(null),
		maxVisibleResults = 6,
		noResultsMessage = 'No matches found.',
		onSelect,
		id = createAutocompleteId(),
		class: className = '',
		autocomplete = 'off',
		...restProps
	}: AutocompleteInputProps = $props();

	let isOpen = $state(false);
	let activeIndex = $state(-1);

	const effectiveTone = $derived(tone ?? (error ? 'danger' : 'primary'));
	const listboxId = $derived(`${id}-listbox`);
	const describedBy = $derived(
		[hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') ||
			undefined
	);
	const classes = $derived(
		`${getControlClasses({ tone: effectiveTone, size: inputSize })}${className ? ` ${className}` : ''}`
	);
	const filteredOptions = $derived(
		filterAutocompleteOptions(options, value).slice(0, maxVisibleResults)
	);
	const activeDescendant = $derived(
		activeIndex >= 0 && filteredOptions[activeIndex]
			? `${id}-option-${filteredOptions[activeIndex].value}`
			: undefined
	);

	const openMenu = () => {
		isOpen = true;
	};

	const closeMenu = () => {
		isOpen = false;
		activeIndex = -1;
	};

	const selectOption = (option: ControlOption) => {
		value = option.label;
		selectedValue = option.value;
		onSelect?.(option);
		closeMenu();
	};

	const handleInput = () => {
		if (selectedValue !== null) {
			selectedValue = null;
		}
		openMenu();
		activeIndex = filteredOptions.length > 0 ? 0 : -1;
	};

	const handleKeydown = (event: KeyboardEvent) => {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			openMenu();
			activeIndex = getNextActiveIndex({
				currentIndex: activeIndex,
				direction: 1,
				optionCount: filteredOptions.length
			});
			return;
		}

		if (event.key === 'ArrowUp') {
			event.preventDefault();
			openMenu();
			activeIndex = getNextActiveIndex({
				currentIndex: activeIndex,
				direction: -1,
				optionCount: filteredOptions.length
			});
			return;
		}

		if (event.key === 'Enter' && isOpen && activeIndex >= 0 && filteredOptions[activeIndex]) {
			event.preventDefault();
			selectOption(filteredOptions[activeIndex]);
			return;
		}

		if (event.key === 'Escape') {
			event.preventDefault();
			closeMenu();
		}
	};

	const handleBlur = () => {
		setTimeout(() => {
			closeMenu();
		}, 100);
	};
</script>

<label class="flex w-full flex-col gap-2">
	{#if label}
		<span class="text-sm font-medium text-text">{label}</span>
	{/if}

	<div class="relative">
		<input
			{...restProps}
			{id}
			{placeholder}
			{autocomplete}
			bind:value
			class={classes}
			role="combobox"
			aria-invalid={error ? 'true' : undefined}
			aria-describedby={describedBy}
			aria-expanded={isOpen ? 'true' : 'false'}
			aria-controls={listboxId}
			aria-activedescendant={activeDescendant}
			data-tone={effectiveTone}
			onfocus={openMenu}
			oninput={handleInput}
			onkeydown={handleKeydown}
			onblur={handleBlur}
		/>

		{#if isOpen}
			<div
				id={listboxId}
				role="listbox"
				class="absolute z-20 mt-2 max-h-64 w-full overflow-auto rounded-3xl border border-border bg-surface-elevated p-2 shadow-[var(--shadow-panel)]"
			>
				{#if filteredOptions.length > 0}
					{#each filteredOptions as option, index (option.value)}
						<button
							type="button"
							id={`${id}-option-${option.value}`}
							role="option"
							class={`flex w-full flex-col rounded-2xl px-3 py-2 text-left transition ${index === activeIndex ? 'bg-primary/15 text-text' : 'text-text-muted hover:bg-surface hover:text-text'}`}
							aria-selected={index === activeIndex}
							onmousedown={(event) => {
								event.preventDefault();
								selectOption(option);
							}}
						>
							<span class="text-sm font-medium">{option.label}</span>
							{#if option.description}
								<span class="text-xs leading-5 text-text-muted">{option.description}</span>
							{/if}
						</button>
					{/each}
				{:else}
					<div class="rounded-2xl px-3 py-2 text-sm text-text-muted">{noResultsMessage}</div>
				{/if}
			</div>
		{/if}
	</div>

	{#if hint}
		<span id={`${id}-hint`} class="text-xs leading-5 text-text-muted">{hint}</span>
	{/if}

	{#if error}
		<span id={`${id}-error`} class="text-xs leading-5 font-medium text-danger">{error}</span>
	{/if}
</label>
