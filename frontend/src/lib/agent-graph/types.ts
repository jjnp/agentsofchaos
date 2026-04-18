import * as v from 'valibot';

export type AgentNodeId = string & { readonly __brand: 'AgentNodeId' };
export const agentNodeStatuses = ['running', 'completed'] as const;
export type AgentNodeStatus = (typeof agentNodeStatuses)[number];

export type AgentNodeContextUsage = Readonly<{
	tokens: number;
	percentage: number;
}>;

export type AgentNodeDetails = Readonly<{
	contextUsage: AgentNodeContextUsage;
}>;

export type AgentNode = Readonly<{
	id: AgentNodeId;
	name: string;
	parentId: AgentNodeId | null;
	status: AgentNodeStatus;
	details: AgentNodeDetails | null;
}>;

export type AgentNodePlacement = Readonly<{
	nodeId: AgentNodeId;
	x: number;
	y: number;
}>;

export const layoutModes = ['rings', 'tree', 'force'] as const;
export type LayoutMode = (typeof layoutModes)[number];

export const agentNodeIdSchema = v.pipe(v.string(), v.uuid());
export const agentNodeStatusSchema = v.picklist(agentNodeStatuses);

export const agentNodeContextUsageSchema = v.object({
	tokens: v.pipe(v.number(), v.integer(), v.minValue(0)),
	percentage: v.pipe(v.number(), v.minValue(0), v.maxValue(100))
});

export const agentNodeDetailsSchema = v.object({
	contextUsage: agentNodeContextUsageSchema
});

export const agentNodeSchema = v.object({
	id: agentNodeIdSchema,
	name: v.pipe(v.string(), v.minLength(1)),
	parentId: v.nullable(agentNodeIdSchema),
	status: agentNodeStatusSchema,
	details: v.nullable(agentNodeDetailsSchema)
});

export const agentNodePlacementSchema = v.object({
	nodeId: agentNodeIdSchema,
	x: v.number(),
	y: v.number()
});

export const isAgentNodeId = (value: string): value is AgentNodeId =>
	v.safeParse(agentNodeIdSchema, value).success;

export const createAgentNodeId = (value: string = crypto.randomUUID()): AgentNodeId => {
	if (!isAgentNodeId(value)) {
		throw new TypeError(`Invalid agent node id: ${value}`);
	}

	return value as AgentNodeId;
};

export const createAgentNode = (input: {
	id?: string;
	name: string;
	parentId?: string | null;
	status: AgentNodeStatus;
	details?: {
		contextUsage: {
			tokens: number;
			percentage: number;
		};
	} | null;
}): AgentNode => {
	const parsedNode = v.parse(agentNodeSchema, {
		id: input.id ?? createAgentNodeId(),
		name: input.name,
		parentId: input.parentId ?? null,
		status: input.status,
		details: input.details
			? {
					contextUsage: input.details.contextUsage
				}
			: null
	});

	return {
		...parsedNode,
		id: parsedNode.id as AgentNodeId,
		parentId: parsedNode.parentId as AgentNodeId | null,
		status: parsedNode.status as AgentNodeStatus,
		details: parsedNode.details as AgentNodeDetails | null
	};
};

export const createAgentNodePlacement = (input: {
	nodeId: string;
	x: number;
	y: number;
}): AgentNodePlacement => {
	const parsedPlacement = v.parse(agentNodePlacementSchema, input);

	return {
		...parsedPlacement,
		nodeId: parsedPlacement.nodeId as AgentNodeId
	};
};
