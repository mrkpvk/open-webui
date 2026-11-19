import { afterEach, describe, expect, it, vi } from 'vitest';

// The history helper does not depend on the browser's app URL.
vi.mock('$lib/constants', () => ({ WEBUI_BASE_URL: '' }));

import { createMessagesList } from './index';

afterEach(() => vi.restoreAllMocks());

// A broken guard should fail the test instead of hanging its worker indefinitely.
const boundedMessages = <T extends Record<string, unknown>>(messages: T): T => {
	let reads = 0;
	return new Proxy(messages, {
		get(target, key, receiver) {
			if (++reads > 10) throw new Error('History traversal did not terminate');
			return Reflect.get(target, key, receiver);
		}
	});
};

describe('conversation parent traversal', () => {
	it('keeps the selected branch in order with original metadata and references', () => {
		const root = Object.freeze({
			id: 'root',
			parentId: null,
			childrenIds: Object.freeze(['chosen', 'alternative']),
			files: Object.freeze([{ id: 'attachment' }]),
			paramsOverride: Object.freeze({ num_gpu: 0, seed: 0, temperature: 0 })
		});
		const chosen = Object.freeze({ id: 'chosen', parentId: 'root', content: 'Selected' });
		const alternative = Object.freeze({ id: 'alternative', parentId: 'root', content: 'Other' });
		const messages = Object.freeze({ root, chosen, alternative });
		const history = Object.freeze({ currentId: 'chosen', messages });
		const list = createMessagesList(history, history.currentId);
		expect(list).toEqual([root, chosen]);
		expect(list[0]).toBe(root);
		expect(list[1]).toBe(chosen);
		expect(history.messages.alternative).toBe(alternative);
	});

	it('stops at missing parents and accepts empty selections', () => {
		const message = { id: 'orphan', parentId: 'missing' };
		const history = { messages: { orphan: message } };
		expect(createMessagesList(history, 'orphan')).toEqual([message]);
		for (const id of [null, undefined, 'missing']) {
			expect(createMessagesList(history, id)).toEqual([]);
		}
	});

	it('stops a self-loop without duplicating or changing its message', () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		const message = Object.freeze({ id: 'self', parentId: 'self', content: 'Keep me' });
		expect(createMessagesList({ messages: boundedMessages({ self: message }) }, 'self')).toEqual([
			message
		]);
		expect(warn).toHaveBeenCalledOnce();
	});

	it('stops a longer cycle after each reachable message is included once', () => {
		const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
		const first = Object.freeze({ id: 'first', parentId: 'second' });
		const second = Object.freeze({ id: 'second', parentId: 'first' });
		const tail = Object.freeze({ id: 'tail', parentId: 'first' });
		const history = Object.freeze({
			messages: boundedMessages(Object.freeze({ first, second, tail }))
		});
		expect(createMessagesList(history, 'tail')).toEqual([second, first, tail]);
		expect(warn).toHaveBeenCalledOnce();
	});
});
