import * as v from 'valibot';

export type AgentNodeId = string & { readonly __brand: 'AgentNodeId' };

export type AgentNode = Readonly<{
	id: AgentNodeId;
	name: string;
	parentId: AgentNodeId | null;
}>;

export type AgentNodePlacement = Readonly<{
	nodeId: AgentNodeId;
	x: number;
	y: number;
}>;

export const layoutModes = ['rings', 'tree', 'force'] as const;
export type LayoutMode = (typeof layoutModes)[number];

export const agentNodeIdSchema = v.pipe(v.string(), v.uuid());

export const agentNodeSchema = v.object({
	id: agentNodeIdSchema,
	name: v.pipe(v.string(), v.minLength(1)),
	parentId: v.nullable(agentNodeIdSchema)
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
}): AgentNode => {
	const parsedNode = v.parse(agentNodeSchema, {
		id: input.id ?? createAgentNodeId(),
		name: input.name,
		parentId: input.parentId ?? null
	});

	return {
		...parsedNode,
		id: parsedNode.id as AgentNodeId,
		parentId: parsedNode.parentId as AgentNodeId | null
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
