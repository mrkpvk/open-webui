import { describe, expect, it } from 'vitest';
import { detectNgramRepetition } from './ngram';

describe('post-generation repetition detection', () => {
	it('finds overlapping repeated phrases', () => {
		expect(detectNgramRepetition('a a a', 2)).toBe('a a');
	});
	it('supports non-ASCII words without collapsing them', () => {
		expect(detectNgramRepetition('déjà vu — déjà vu', 2)).toBe('déjà vu');
		expect(detectNgramRepetition('α β γ δ', 2)).toBeNull();
	});
	it('ignores case and punctuation', () => {
		expect(detectNgramRepetition('Hello world! HELLO, world.', 2)).toBe('hello world');
	});
	it('rejects invalid sizes and does not warn for unique or insufficient words', () => {
		for (const n of [0, 1, 2.5, NaN, Infinity]) {
			expect(detectNgramRepetition('a a a a', n)).toBeNull();
		}
		expect(detectNgramRepetition('one two three', 2)).toBeNull();
		expect(detectNgramRepetition('one two', 2)).toBeNull();
	});
});
