import { describe, expect, it } from 'vitest';
import { normalizeStopTokens, resolveMessageParams } from './messageParams';

describe('generation parameter resolution', () => {
	it('inherits nulls and respects global, chat, user and response precedence', () => {
		expect(
			resolveMessageParams(
				{ seed: 12, temperature: 0.7, num_gpu: 20, stop: ['END'] },
				{ seed: null, temperature: 0.3, num_gpu: 0 },
				{ seed: 0, temperature: null, stream_response: false },
				{ temperature: 0, stop: [] }
			)
		).toEqual({ seed: 0, temperature: 0, num_gpu: 0, stream_response: false, stop: [] });
	});

	it('does not modify saved settings while resolving', () => {
		const settings = { seed: 0, temperature: null };
		resolveMessageParams(settings, { temperature: 0.5 });
		expect(settings).toEqual({ seed: 0, temperature: null });
	});

	it('normalizes message stop strings using the same rules as chat defaults', () => {
		expect(normalizeStopTokens('END, \\n, %3Cstop%3E')).toEqual(['END', '\n', '<stop>']);
		expect(normalizeStopTokens(['END', ''])).toEqual(['END']);
		expect(normalizeStopTokens('')).toEqual([]);
		expect(normalizeStopTokens(null)).toBeUndefined();
	});

	it('preserves literal percent signs and malformed escapes', () => {
		expect(normalizeStopTokens('100%, \\x')).toEqual(['100%', '\\x']);
	});

	it('preserves literal stop lists including whitespace, commas and percent escapes', () => {
		const stop = ['\n', ' END ', ',', '%3Cstop%3E', ''];
		expect(normalizeStopTokens(stop)).toEqual(['\n', ' END ', ',', '%3Cstop%3E']);
		expect(stop).toEqual(['\n', ' END ', ',', '%3Cstop%3E', '']);
	});
});
