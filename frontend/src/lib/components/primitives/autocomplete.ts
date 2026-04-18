import type { ControlOption } from './types';

const normalize = (value: string) => value.trim().toLocaleLowerCase();

export const filterAutocompleteOptions = (
	options: readonly ControlOption[],
	query: string
): ControlOption[] => {
	const normalizedQuery = normalize(query);

	if (normalizedQuery.length === 0) {
		return [...options].filter((option) => !option.disabled);
	}

	return options.filter((option) => {
		if (option.disabled) {
			return false;
		}

		const haystacks = [option.label, option.value, option.description ?? ''];
		return haystacks.some((field) => normalize(field).includes(normalizedQuery));
	});
};

export const getNextActiveIndex = ({
	currentIndex,
	direction,
	optionCount
}: {
	currentIndex: number;
	direction: 1 | -1;
	optionCount: number;
}) => {
	if (optionCount === 0) {
		return -1;
	}

	if (currentIndex < 0) {
		return direction === 1 ? 0 : optionCount - 1;
	}

	return (currentIndex + direction + optionCount) % optionCount;
};
