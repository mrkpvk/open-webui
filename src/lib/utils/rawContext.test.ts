import { describe, expect, it } from 'vitest';
import { applyContextPath, editableContextPath, type ContextHistory } from './rawContext';

const fixture = (): ContextHistory => ({
	currentId: 'answer',
	messages: {
		question: {
			id: 'question',
			parentId: null,
			childrenIds: ['answer', 'alternative'],
			role: 'user',
			content: 'Question',
			models: ['local-model'],
			files: [{ id: 'attachment' }],
			paramsOverride: { seed: 0, num_gpu: 0 }
		},
		answer: {
			id: 'answer',
			parentId: 'question',
			childrenIds: [],
			role: 'assistant',
			content: 'Old answer',
			model: 'local-model',
			done: true,
			output: [{ type: 'message', content: [{ type: 'output_text', text: 'Old answer' }] }]
		},
		alternative: {
			id: 'alternative',
			parentId: 'question',
			childrenIds: [],
			role: 'assistant',
			content: 'Alternative',
			model: 'other-model',
			done: true
		}
	}
});

describe('raw context edits', () => {
	it('preserves other branches, attachments and CPU overrides without mutating history', () => {
		const history = fixture();
		const original = structuredClone(history);
		const path = editableContextPath(history);
		path[1].content = 'Edited answer';
		let id = 0;
		const edited = applyContextPath(history, path, () => `new-${++id}`);
		expect(history).toEqual(original);
		for (const [key, message] of Object.entries(original.messages)) {
			expect(edited.messages[key]).toEqual(message);
		}
		expect(edited.currentId).toBe('new-2');
		expect(edited.messages['new-1']).toMatchObject({
			parentId: null,
			childrenIds: ['new-2'],
			files: [{ id: 'attachment' }],
			models: ['local-model'],
			paramsOverride: { seed: 0, num_gpu: 0 }
		});
		expect(edited.messages['new-2']).toMatchObject({
			parentId: 'new-1',
			childrenIds: [],
			content: 'Edited answer',
			model: 'local-model',
			done: true
		});
		expect(edited.messages['new-2'].output).toBeUndefined();
	});

	it('keeps structured output when its text and role are unchanged', () => {
		const history = fixture();
		const edited = applyContextPath(
			history,
			editableContextPath(history),
			(() => {
				let id = 0;
				return () => `copy-${++id}`;
			})()
		);
		expect(edited.messages['copy-2'].output).toEqual(history.messages.answer.output);
	});

	it('relinks reordered and inserted messages and marks pasted responses complete', () => {
		const history = fixture();
		const path = editableContextPath(history).reverse();
		path.push({ id: 'draft', role: 'assistant', content: 'Pasted answer' });
		let id = 0;
		const edited = applyContextPath(history, path, () => `copy-${++id}`);
		expect(edited.messages['copy-1'].parentId).toBeNull();
		expect(edited.messages['copy-2'].childrenIds).toEqual(['copy-3']);
		expect(edited.messages['copy-3']).toMatchObject({
			parentId: 'copy-2',
			done: true,
			childrenIds: []
		});
	});

	it('rejects empty paths and malformed cyclic or missing parent chains', () => {
		expect(() => applyContextPath(fixture(), [])).toThrow();
		const history = fixture();
		history.messages.question.parentId = 'answer';
		expect(() => editableContextPath(history)).toThrow('cycle');
		history.messages.question.parentId = 'missing';
		expect(() => editableContextPath(history)).toThrow('missing');
	});
});
