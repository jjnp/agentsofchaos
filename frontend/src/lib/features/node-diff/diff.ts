import * as v from 'valibot';

import {
	fileDiffSchema,
	type DiffHunk,
	type DiffLine,
	type FileChangeType,
	type FileDiff
} from './schemas';

const HUNK_HEADER = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;

function normalizePath(path: string) {
	return path.replace(/^[ab]\//, '');
}

function detectChangeType(oldPath: string, newPath: string): FileChangeType {
	if (oldPath === '/dev/null') return 'added';
	if (newPath === '/dev/null') return 'deleted';
	if (normalizePath(oldPath) !== normalizePath(newPath)) return 'renamed';
	return 'modified';
}

function createEmptyFile(path = ''): FileDiff {
	return {
		path,
		oldPath: path,
		newPath: path,
		changeType: 'modified',
		additions: 0,
		deletions: 0,
		hunks: []
	};
}

function finalizeFile(file: FileDiff | null) {
	if (!file) return null;

	const resolvedPath =
		file.changeType === 'deleted'
			? normalizePath(file.oldPath)
			: normalizePath(file.newPath || file.oldPath);

	return v.parse(fileDiffSchema, {
		...file,
		path: resolvedPath,
		oldPath: normalizePath(file.oldPath),
		newPath: normalizePath(file.newPath)
	});
}

export function parseUnifiedDiff(diff: string): FileDiff[] {
	const lines = diff.replace(/\r\n/g, '\n').split('\n');
	const files: FileDiff[] = [];
	let currentFile: FileDiff | null = null;
	let currentHunk: DiffHunk | null = null;

	const pushCurrentHunk = () => {
		if (!currentFile || !currentHunk) return;
		currentFile.hunks.push(currentHunk);
		currentHunk = null;
	};

	const pushCurrentFile = () => {
		pushCurrentHunk();
		const finalized = finalizeFile(currentFile);
		if (finalized) files.push(finalized);
		currentFile = null;
	};

	for (const line of lines) {
		if (line.startsWith('diff --git ')) {
			pushCurrentFile();
			const [, aPath = '', bPath = ''] = /^diff --git a\/(.+) b\/(.+)$/.exec(line) ?? [];
			currentFile = createEmptyFile(normalizePath(bPath || aPath));
			currentFile.oldPath = aPath;
			currentFile.newPath = bPath;
			currentFile.changeType = detectChangeType(aPath, bPath);
			continue;
		}

		if (!currentFile) continue;

		if (line.startsWith('rename from ')) {
			currentFile.oldPath = line.slice('rename from '.length);
			currentFile.changeType = detectChangeType(currentFile.oldPath, currentFile.newPath);
			continue;
		}

		if (line.startsWith('rename to ')) {
			currentFile.newPath = line.slice('rename to '.length);
			currentFile.changeType = detectChangeType(currentFile.oldPath, currentFile.newPath);
			continue;
		}

		if (line.startsWith('--- ')) {
			currentFile.oldPath = line.slice(4);
			currentFile.changeType = detectChangeType(currentFile.oldPath, currentFile.newPath);
			continue;
		}

		if (line.startsWith('+++ ')) {
			currentFile.newPath = line.slice(4);
			currentFile.changeType = detectChangeType(currentFile.oldPath, currentFile.newPath);
			continue;
		}

		const hunkMatch = HUNK_HEADER.exec(line);
		if (hunkMatch) {
			pushCurrentHunk();
			currentHunk = {
				header: line,
				oldStart: Number(hunkMatch[1]),
				oldLines: Number(hunkMatch[2] ?? '1'),
				newStart: Number(hunkMatch[3]),
				newLines: Number(hunkMatch[4] ?? '1'),
				lines: []
			};
			continue;
		}

		if (!currentHunk) continue;
		if (line.startsWith('\\ No newline at end of file')) continue;

		let nextLine: DiffLine | null = null;
		if (line.startsWith('+')) {
			currentFile.additions += 1;
			nextLine = { type: 'add', content: line.slice(1) };
		} else if (line.startsWith('-')) {
			currentFile.deletions += 1;
			nextLine = { type: 'remove', content: line.slice(1) };
		} else if (line.startsWith(' ')) {
			nextLine = { type: 'context', content: line.slice(1) };
		}

		if (nextLine) currentHunk.lines.push(nextLine);
	}

	pushCurrentFile();
	return files;
}

export function summarizeDiffTotals(files: FileDiff[]) {
	return files.reduce(
		(totals, file) => ({
			files: totals.files + 1,
			additions: totals.additions + file.additions,
			deletions: totals.deletions + file.deletions
		}),
		{ files: 0, additions: 0, deletions: 0 }
	);
}
