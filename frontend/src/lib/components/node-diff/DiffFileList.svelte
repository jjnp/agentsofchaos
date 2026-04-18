<script lang="ts">
	import type { FileDiff } from '$lib/features/node-diff/schemas';

	interface Props {
		files: FileDiff[];
		selectedPath: string | null;
		onSelect: (path: string) => void;
	}

	interface DirectoryNode {
		kind: 'directory';
		name: string;
		path: string;
		children: Array<TreeNode>;
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
				current.children.push({
					kind: 'file',
					name: segment,
					path,
					file
				});
				continue;
			}

			let next = current.children.find(
				(child): child is DirectoryNode => child.kind === 'directory' && child.name === segment
			);
			if (!next) {
				next = {
					kind: 'directory',
					name: segment,
					path,
					children: []
				};
				current.children.push(next);
			}
			current = next;
		}
	}

	function sortTree(node: DirectoryNode) {
		node.children.sort((left, right) => {
			if (left.kind !== right.kind) return left.kind === 'directory' ? -1 : 1;
			return left.name.localeCompare(right.name);
		});

		for (const child of node.children) {
			if (child.kind === 'directory') sortTree(child);
		}
	}

	function compressDirectory(node: DirectoryNode): DirectoryNode {
		const compressedChildren = node.children.map((child) =>
			child.kind === 'directory' ? compressDirectory(child) : child
		);

		let nextNode: DirectoryNode = { ...node, children: compressedChildren };
		while (nextNode.children.length === 1 && nextNode.children[0]?.kind === 'directory') {
			const onlyChild = nextNode.children[0];
			nextNode = {
				kind: 'directory',
				name: `${nextNode.name}/${onlyChild.name}`,
				path: onlyChild.path,
				children: onlyChild.children
			};
		}

		return nextNode;
	}

	function buildTree(files: FileDiff[]) {
		const root: DirectoryNode = { kind: 'directory', name: '', path: '', children: [] };
		for (const file of files) insertFile(root, file);
		sortTree(root);
		return root.children.map((child) =>
			child.kind === 'directory' ? compressDirectory(child) : child
		);
	}

	function flattenTree(nodes: TreeNode[], depth = 0): TreeRow[] {
		const rows: TreeRow[] = [];

		for (const node of nodes) {
			if (node.kind === 'directory') {
				const isCollapsed = collapsedPaths[node.path] ?? false;
				rows.push({
					id: `dir:${node.path}`,
					depth,
					kind: 'directory',
					label: node.name,
					path: node.path,
					collapsed: isCollapsed
				});
				if (!isCollapsed) {
					rows.push(...flattenTree(node.children, depth + 1));
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

	function toggleDirectory(path: string) {
		collapsedPaths = {
			...collapsedPaths,
			[path]: !(collapsedPaths[path] ?? false)
		};
	}

	function expandSelectedAncestors(path: string | null) {
		if (!path) return;
		const segments = path.split('/');
		const nextCollapsed = { ...collapsedPaths };
		let changed = false;
		for (let index = 0; index < segments.length - 1; index += 1) {
			const parentPath = segments.slice(0, index + 1).join('/');
			if (nextCollapsed[parentPath] === false) continue;
			nextCollapsed[parentPath] = false;
			changed = true;
		}
		if (changed) {
			collapsedPaths = nextCollapsed;
		}
	}

	const tree = $derived(buildTree(files));
	const rows = $derived(flattenTree(tree));

	$effect(() => {
		expandSelectedAncestors(selectedPath);
	});
</script>

<nav class="flex h-full flex-col gap-1 overflow-y-auto pr-1" aria-label="Changed files">
	{#each rows as row (row.id)}
		{#if row.kind === 'directory'}
			<button
				type="button"
				class="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-xs text-text-muted transition hover:bg-surface-elevated/60 hover:text-text"
				style={`padding-left: ${row.depth * 0.875 + 0.5}rem`}
				aria-label={row.path}
				onclick={() => toggleDirectory(row.path)}
			>
				<span aria-hidden="true">{row.collapsed ? '▸' : '▾'}</span>
				<span class="truncate">{row.label}</span>
			</button>
		{:else if row.file}
			<button
				type="button"
				class={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition ${selectedPath === row.path ? 'bg-primary/10 text-text' : 'text-text-muted hover:bg-surface-elevated/80 hover:text-text'}`}
				style={`padding-left: ${row.depth * 0.875 + 0.5}rem`}
				aria-label={row.path}
				onclick={() => onSelect(row.path)}
			>
				<div class="min-w-0 truncate">{row.label}</div>
				<div class="flex items-center gap-2 text-[11px] font-medium">
					<span class="text-success">+{row.file.additions}</span>
					<span class="text-danger">-{row.file.deletions}</span>
				</div>
			</button>
		{/if}
	{/each}
</nav>
