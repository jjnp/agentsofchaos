import * as v from 'valibot';

export type Brand<T, Name extends string> = T & { readonly __brand: Name };
export type NodeId = Brand<string, 'NodeId'>;

export const nodeIdSchema = v.pipe(v.string(), v.minLength(1));

export const diffLineTypeSchema = v.picklist(['context', 'add', 'remove']);
export type DiffLineType = v.InferOutput<typeof diffLineTypeSchema>;

export const diffLineSchema = v.object({
	type: diffLineTypeSchema,
	content: v.string()
});
export type DiffLine = v.InferOutput<typeof diffLineSchema>;

export const diffHunkSchema = v.object({
	header: v.string(),
	oldStart: v.number(),
	oldLines: v.number(),
	newStart: v.number(),
	newLines: v.number(),
	lines: v.array(diffLineSchema)
});
export type DiffHunk = v.InferOutput<typeof diffHunkSchema>;

export const fileChangeTypeSchema = v.picklist(['modified', 'added', 'deleted', 'renamed']);
export type FileChangeType = v.InferOutput<typeof fileChangeTypeSchema>;

export const fileDiffSchema = v.object({
	path: v.string(),
	oldPath: v.string(),
	newPath: v.string(),
	changeType: fileChangeTypeSchema,
	additions: v.number(),
	deletions: v.number(),
	hunks: v.array(diffHunkSchema)
});
export type FileDiff = v.InferOutput<typeof fileDiffSchema>;

export const nodeDiffOverviewRequestSchema = v.object({
	nodeId: v.optional(nodeIdSchema),
	prompt: v.string(),
	diff: v.string(),
	context: v.optional(v.string())
});
export type NodeDiffOverviewRequest = v.InferInput<typeof nodeDiffOverviewRequestSchema>;

export const fileSummaryRequestSchema = v.object({
	nodeId: v.optional(nodeIdSchema),
	prompt: v.string(),
	file: fileDiffSchema,
	context: v.optional(v.string())
});
export type FileSummaryRequest = v.InferInput<typeof fileSummaryRequestSchema>;

export const nodeDiffOverviewSchema = v.object({
	nodeId: v.optional(nodeIdSchema),
	prompt: v.string(),
	overallSummary: v.string(),
	overallSummaryCached: v.boolean(),
	files: v.array(fileDiffSchema),
	totals: v.object({
		files: v.number(),
		additions: v.number(),
		deletions: v.number()
	})
});
export type NodeDiffOverview = v.InferOutput<typeof nodeDiffOverviewSchema>;

export const fileSummaryResponseSchema = v.object({
	path: v.string(),
	summary: v.string(),
	cached: v.boolean()
});
export type FileSummaryResponse = v.InferOutput<typeof fileSummaryResponseSchema>;
