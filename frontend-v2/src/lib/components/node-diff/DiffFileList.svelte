<script lang="ts">
	import type { FileDiff } from '$lib/orchestrator/contracts';

	interface Props {
		files: readonly FileDiff[];
		selectedPath: string | null;
		onSelect: (path: string) => void;
	}

	interface DirectoryNode {
		kind: 'directory';
		name: string;
		path: string;
		children: TreeNode[];
	}

	interface FileNode {
		kind: 'file';
		name: string;
		path: string;
		file: FileDiff;
	}

	type TreeNode = DirectoryNode | FileNode;

	interface TreeRow {
		id: string;
		depth: number;
		kind: 'directory' | 'file';
		label: string;
		path: string;
		file?: FileDiff;
		collapsed?: boolean;
	}

	let { files, selectedPath, onSelect }: Props = $props();
	let collapsedPaths = $state<Record<string, boolean>>({});

	function insertFile(root: DirectoryNode, file: FileDiff) {
		const segments = file.path.split('/');
		let current = root;
		for (const [index, segment] of segments.entries()) {
			const path = segments.slice(0, index + 1).join('/');
			const isLeaf = index === segments.length - 1;
			if (isLeaf) {
				current.children.push({ kind: 'file', name: segment, path, file });
				continue;
			}
			let next = current.children.find(
				(child): child is DirectoryNode =>
					child.kind === 'directory' && child.name === segment
			);
			if (!next) {
				next = { kind: 'directory', name: segment, path, children: [] };
				current.children.push(next);
			}
			current = next;
		}
	}

	function sortTree(node: DirectoryNode) {
		node.children.sort((a, b) => {
			if (a.kind !== b.kind) return a.kind === 'directory' ? -1 : 1;
			return a.name.localeCompare(b.name);
		});
		for (const child of node.children) {
			if (child.kind === 'directory') sortTree(child);
		}
	}

	function compress(node: DirectoryNode): DirectoryNode {
		const children = node.children.map((child) =>
			child.kind === 'directory' ? compress(child) : child
		);
		let next: DirectoryNode = { ...node, children };
		while (next.children.length === 1 && next.children[0]?.kind === 'directory') {
			const only = next.children[0];
			next = {
				kind: 'directory',
				name: `${next.name}/${only.name}`,
				path: only.path,
				children: only.children
			};
		}
		return next;
	}

	function buildTree(input: readonly FileDiff[]): TreeNode[] {
		const root: DirectoryNode = { kind: 'directory', name: '', path: '', children: [] };
		for (const file of input) insertFile(root, file);
		sortTree(root);
		return root.children.map((child) =>
			child.kind === 'directory' ? compress(child) : child
		);
	}

	function flatten(nodes: TreeNode[], depth = 0): TreeRow[] {
		const rows: TreeRow[] = [];
		for (const node of nodes) {
			if (node.kind === 'directory') {
				const collapsed = collapsedPaths[node.path] ?? false;
				rows.push({
					id: `dir:${node.path}`,
					depth,
					kind: 'directory',
					label: node.name,
					path: node.path,
					collapsed
				});
				if (!collapsed) {
					rows.push(...flatten(node.children, depth + 1));
				}
				continue;
			}
			rows.push({
				id: `file:${node.path}`,
				depth,
				kind: 'file',
				label: node.name,
				path: node.path,
				file: node.file
			});
		}
		return rows;
	}

	function toggleDir(path: string) {
		collapsedPaths = { ...collapsedPaths, [path]: !(collapsedPaths[path] ?? false) };
	}

	function expandAncestors(path: string | null) {
		if (!path) return;
		const segments = path.split('/');
		const next = { ...collapsedPaths };
		let changed = false;
		for (let i = 0; i < segments.length - 1; i += 1) {
			const parent = segments.slice(0, i + 1).join('/');
			if (next[parent] === false) continue;
			next[parent] = false;
			changed = true;
		}
		if (changed) collapsedPaths = next;
	}

	const tree = $derived(buildTree(files));
	const rows = $derived(flatten(tree));

	$effect(() => {
		expandAncestors(selectedPath);
	});
</script>

<nav class="filelist" aria-label="Changed files">
	{#each rows as row (row.id)}
		{#if row.kind === 'directory'}
			<button
				type="button"
				class="dir"
				style="padding-left: {row.depth * 0.875 + 0.5}rem"
				aria-label={row.path}
				onclick={() => toggleDir(row.path)}
			>
				<span aria-hidden="true">{row.collapsed ? '▸' : '▾'}</span>
				<span class="truncate">{row.label}</span>
			</button>
		{:else if row.file}
			<button
				type="button"
				class="file"
				class:selected={selectedPath === row.path}
				style="padding-left: {row.depth * 0.875 + 0.5}rem"
				aria-label={row.path}
				onclick={() => onSelect(row.path)}
			>
				<span class="truncate">{row.label}</span>
				<span class="counts">
					<span class="add">+{row.file.additions}</span>
					<span class="del">-{row.file.deletions}</span>
				</span>
			</button>
		{/if}
	{/each}
</nav>

<style>
	.filelist {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		overflow-y: auto;
		padding-right: 0.25rem;
		min-height: 0;
	}
	.dir,
	.file {
		display: grid;
		align-items: center;
		gap: 0.4rem;
		width: 100%;
		text-align: left;
		background: none;
		border: 0;
		padding: 0.2rem 0.5rem;
		font: inherit;
		color: var(--color-text-muted);
		cursor: pointer;
		transition: background-color 120ms ease, color 120ms ease;
		border-radius: 0.5rem;
		font-size: 0.78rem;
	}
	.dir {
		grid-template-columns: 0.7rem 1fr;
	}
	.file {
		grid-template-columns: minmax(0, 1fr) auto;
	}
	.dir:hover,
	.file:hover {
		background: color-mix(in srgb, var(--color-surface-elevated) 70%, transparent);
		color: var(--color-text);
	}
	.file.selected {
		background: color-mix(in srgb, var(--color-primary) 14%, transparent);
		color: var(--color-text);
	}
	.truncate {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.counts {
		display: inline-flex;
		gap: 0.4rem;
		font-size: 0.7rem;
		font-family: var(--font-mono);
	}
	.add {
		color: var(--color-success);
	}
	.del {
		color: var(--color-danger);
	}
</style>
