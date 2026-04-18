export interface PiSummaryStep {
	label: string;
	status: 'done' | 'pending' | 'note';
}

export interface PiSummaryBlock {
	type: 'paragraph' | 'bullet-list' | 'progress-steps';
	content: string[];
	steps?: PiSummaryStep[];
}

export interface PiSummarySection {
	id: string;
	title: string;
	blocks: PiSummaryBlock[];
}

export interface PiSummaryDocument {
	title: string;
	sections: PiSummarySection[];
}

function slugify(value: string) {
	return value
		.toLowerCase()
		.trim()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '');
}

function createBlock(lines: string[], sectionTitle: string): PiSummaryBlock | null {
	const normalized = lines.map((line) => line.trim()).filter(Boolean);
	if (normalized.length === 0) return null;

	const progressSteps = normalized
		.map((line) => {
			const checkbox = /^[-*]\s+\[(x| )\]\s+(.+)$/i.exec(line);
			if (checkbox) {
				return {
					label: checkbox[2],
					status: checkbox[1].toLowerCase() === 'x' ? 'done' : 'pending'
				} as PiSummaryStep;
			}

			const bullet = /^[-*]\s+(.+)$/.exec(line);
			if (bullet) {
				return {
					label: bullet[1],
					status: 'note'
				} as PiSummaryStep;
			}

			return null;
		})
		.filter((step) => step !== null);

	if (/progress|steps?/i.test(sectionTitle) && progressSteps.length === normalized.length) {
		return {
			type: 'progress-steps',
			content: normalized,
			steps: progressSteps
		};
	}

	if (normalized.every((line) => /^[-*]\s+/.test(line))) {
		return {
			type: 'bullet-list',
			content: normalized.map((line) => line.replace(/^[-*]\s+/, ''))
		};
	}

	return {
		type: 'paragraph',
		content: [normalized.join(' ')]
	};
}

export function parsePiSummary(markdown: string): PiSummaryDocument {
	const lines = markdown.replace(/\r\n/g, '\n').split('\n');
	let title = 'Pi summary';
	const sections: PiSummarySection[] = [];
	let currentSection: PiSummarySection | null = null;
	let currentBlockLines: string[] = [];

	function pushBlock() {
		if (!currentSection) return;
		const block = createBlock(currentBlockLines, currentSection.title);
		if (block) currentSection.blocks.push(block);
		currentBlockLines = [];
	}

	function pushSection() {
		if (!currentSection) return;
		pushBlock();
		sections.push(currentSection);
		currentSection = null;
	}

	for (const line of lines) {
		if (line.startsWith('# ')) {
			title = line.slice(2).trim() || title;
			continue;
		}

		if (line.startsWith('## ')) {
			pushSection();
			const heading = line.slice(3).trim();
			currentSection = {
				id: slugify(heading),
				title: heading,
				blocks: []
			};
			continue;
		}

		if (!currentSection) continue;

		if (line.trim() === '') {
			pushBlock();
			continue;
		}

		currentBlockLines.push(line);
	}

	pushSection();

	return {
		title,
		sections
	};
}
