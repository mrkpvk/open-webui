export type ContextRole = 'user' | 'assistant' | 'system';
export interface EditableContextMessage {
	id: string;
	sourceId?: string;
	role: ContextRole;
	content: string;
}

export interface ContextHistory {
	currentId: string | null;
	messages: Record<string, any>;
}

export const editableContextPath = (history: ContextHistory): EditableContextMessage[] => {
	const path: EditableContextMessage[] = [];
	const visited = new Set<string>();
	let id = history.currentId;
	while (id) {
		if (visited.has(id)) throw new Error('Conversation contains a cycle');
		visited.add(id);
		const message = history.messages[id];
		if (!message) throw new Error('Conversation contains a missing message');
		path.push({
			id,
			sourceId: id,
			role: message.role,
			content: typeof message.content === 'string' ? message.content : ''
		});
		id = message.parentId;
	}
	return path.reverse();
};

/** Save an edited path as a new branch, keeping every original branch and attachment. */
export const applyContextPath = (
	history: ContextHistory,
	path: EditableContextMessage[],
	makeId: () => string = () => crypto.randomUUID()
): ContextHistory => {
	if (!path.length) throw new Error('Cannot apply an empty conversation');
	const messages = structuredClone(history.messages);
	const ids = path.map(() => makeId());
	for (const [index, editable] of path.entries()) {
		const source = editable.sourceId ? history.messages[editable.sourceId] : undefined;
		const message = {
			...(source ? structuredClone(source) : { timestamp: Math.floor(Date.now() / 1000) }),
			id: ids[index],
			parentId: index === 0 ? null : ids[index - 1],
			childrenIds: index === path.length - 1 ? [] : [ids[index + 1]],
			role: editable.role,
			content: editable.content,
			...(editable.role === 'assistant' ? { done: true } : {})
		};
		if (source && (source.content !== editable.content || source.role !== editable.role)) {
			// Structured output and merged text otherwise override the edited content.
			delete message.output;
			delete message.merged;
		}
		messages[ids[index]] = message;
	}
	return { ...history, currentId: ids.at(-1)!, messages };
};
