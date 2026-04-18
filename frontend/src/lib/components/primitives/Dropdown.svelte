<script lang="ts">
	import type { HTMLButtonAttributes } from 'svelte/elements';

	import { getNextActiveIndex } from './autocomplete';
	import { getControlClasses } from './styles';
	import type { ControlOption, ControlSize, ControlTone } from './types';

	type DropdownProps = Omit<HTMLButtonAttributes, 'size' | 'value'> & {
		label?: string;
		hint?: string;
		error?: string;
		tone?: ControlTone;
		inputSize?: ControlSize;
		placeholder?: string;
		options: readonly ControlOption[];
		value?: string;
		name?: string;
		required?: boolean;
		onSelect?: (option: ControlOption) => void;
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
		name,
		onSelect,
		id = createDropdownId(),
		class: className = '',
		disabled = false,
		required = false,
		...restProps
	}: DropdownProps = $props();

	let isOpen = $state(false);
	let activeIndex = $state(-1);

	const enabledOptions = $derived(options.filter((option) => !option.disabled));
	const selectedOption = $derived(options.find((option) => option.value === value));
	const effectiveTone = $derived(tone ?? (error ? 'danger' : 'primary'));
	const listboxId = $derived(`${id}-listbox`);
	const describedBy = $derived(
		[hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') ||
			undefined
	);
	const classes = $derived(
		`${getControlClasses({ tone: effectiveTone, size: inputSize })} flex items-center justify-between gap-3 text-left ${className ? ` ${className}` : ''}`
	);
	const displayLabel = $derived(selectedOption?.label ?? placeholder);
	const displayDescription = $derived(selectedOption?.description);
	const activeDescendant = $derived(
		activeIndex >= 0 && enabledOptions[activeIndex]
			? `${id}-option-${enabledOptions[activeIndex].value}`
			: undefined
	);

	const openMenu = () => {
		if (disabled) {
			return;
		}

		isOpen = true;
		activeIndex = Math.max(
			enabledOptions.findIndex((option) => option.value === value),
			enabledOptions.length > 0 ? 0 : -1
		);
	};

	const closeMenu = () => {
		isOpen = false;
		activeIndex = -1;
	};

	const toggleMenu = () => {
		if (isOpen) {
			closeMenu();
			return;
		}

		openMenu();
	};

	const selectOption = (option: ControlOption) => {
		value = option.value;
		onSelect?.(option);
		closeMenu();
	};

	const handleKeydown = (event: KeyboardEvent) => {
		if (disabled) {
			return;
		}

		if (event.key === 'ArrowDown') {
			event.preventDefault();
			if (!isOpen) {
				openMenu();
				return;
			}

			activeIndex = getNextActiveIndex({
				currentIndex: activeIndex,
				direction: 1,
				optionCount: enabledOptions.length
			});
			return;
		}

		if (event.key === 'ArrowUp') {
			event.preventDefault();
			if (!isOpen) {
				openMenu();
				return;
			}

			activeIndex = getNextActiveIndex({
				currentIndex: activeIndex,
				direction: -1,
				optionCount: enabledOptions.length
			});
			return;
		}

		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			if (!isOpen) {
				openMenu();
				return;
			}

			if (activeIndex >= 0 && enabledOptions[activeIndex]) {
				selectOption(enabledOptions[activeIndex]);
			}
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

	{#if name}
		<input type="hidden" {name} {value} {required} />
	{/if}

	<div class="relative">
		<button
			{...restProps}
			{id}
			type="button"
			class={classes}
			role="combobox"
			aria-invalid={error ? 'true' : undefined}
			aria-describedby={describedBy}
			aria-expanded={isOpen ? 'true' : 'false'}
			aria-controls={listboxId}
			aria-activedescendant={activeDescendant}
			aria-haspopup="listbox"
			data-tone={effectiveTone}
			{disabled}
			onclick={toggleMenu}
			onkeydown={handleKeydown}
			onblur={handleBlur}
		>
			<span class="min-w-0 flex-1">
				<span
					class:text-text={!selectedOption}
					class:text-text-muted={!selectedOption}
					class="block truncate text-sm font-medium"
				>
					{displayLabel}
				</span>
				{#if displayDescription}
					<span class="mt-0.5 block truncate text-xs leading-5 text-text-muted">
						{displayDescription}
					</span>
				{/if}
			</span>
			<span class={`shrink-0 text-text-muted transition ${isOpen ? 'rotate-180' : ''}`}>▾</span>
		</button>

		{#if isOpen}
			<div
				id={listboxId}
				role="listbox"
				class="absolute z-20 mt-2 max-h-64 w-full overflow-auto rounded-3xl border border-border bg-surface-elevated p-2 shadow-[var(--shadow-panel)]"
			>
				{#each options as option (option.value)}
					<button
						type="button"
						id={`${id}-option-${option.value}`}
						role="option"
						class={`flex w-full flex-col rounded-2xl px-3 py-2 text-left transition ${option.disabled ? 'cursor-not-allowed opacity-45' : option.value === value ? 'bg-primary/15 text-text' : 'text-text-muted hover:bg-surface hover:text-text'}`}
						aria-selected={option.value === value}
						aria-disabled={option.disabled ? 'true' : undefined}
						disabled={option.disabled}
						onmousedown={(event) => {
							event.preventDefault();
							if (!option.disabled) {
								selectOption(option);
							}
						}}
					>
						<span class="text-sm font-medium">{option.label}</span>
						{#if option.description}
							<span class="text-xs leading-5 text-text-muted">{option.description}</span>
						{/if}
					</button>
				{/each}
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
