export type TerminalFeedUpdate =
	| Readonly<{
			mode: 'none';
			text: '';
	  }>
	| Readonly<{
			mode: 'append';
			text: string;
	  }>
	| Readonly<{
			mode: 'replace';
			text: string;
	  }>;

export const getTerminalFeedUpdate = (
	previousText: string,
	nextText: string | null | undefined
): TerminalFeedUpdate => {
	const normalizedNextText = nextText ?? '';
	if (normalizedNextText === previousText) {
		return { mode: 'none', text: '' };
	}

	if (normalizedNextText.startsWith(previousText)) {
		return {
			mode: 'append',
			text: normalizedNextText.slice(previousText.length)
		};
	}

	return {
		mode: 'replace',
		text: normalizedNextText
	};
};
