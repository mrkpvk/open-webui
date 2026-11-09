import { describe, expect, it } from 'vitest';
import {
	parseBenchmarkDataset,
	parseBenchmarkConfigurations,
	parseInferenceSeeds,
	parseBenchmarkCsv
} from './benchmarkDataset';

describe('benchmark imports', () => {
	it('imports JSON arrays, wrapped datasets and JSONL with stable ids', () => {
		const q = { id: 'q', prompt: 'Answer yes.', expected: true };
		expect(parseBenchmarkDataset(JSON.stringify([q]))).toEqual([q]);
		expect(parseBenchmarkDataset(JSON.stringify({ questions: [q] }))).toEqual([q]);
		expect(
			parseBenchmarkDataset(JSON.stringify(q) + '\n' + JSON.stringify({ ...q, id: 'q2' }))
		).toHaveLength(2);
	});
	it('handles quoted CSV commas, quotes, multiline prompts and boolean labels', () => {
		const text = 'id,prompt,expected\r\nq1,"Say ""yes"", please\nnow",true\r\n';
		expect(parseBenchmarkDataset(text)[0]).toMatchObject({
			id: 'q1',
			prompt: 'Say "yes", please\nnow',
			expected: true
		});
		expect(() => parseBenchmarkCsv('a,"unclosed')).toThrow();
	});
	it('rejects duplicate ids, missing prompts and malformed CSV rows', () => {
		expect(() =>
			parseBenchmarkDataset('[{"id":"x","prompt":"a"},{"id":"x","prompt":"b"}]')
		).toThrow('duplicate');
		expect(() => parseBenchmarkDataset('[{"expected":"a"}]')).toThrow('prompt');
		expect(() => parseBenchmarkDataset('id,prompt\nx,a,b')).toThrow('fields');
	});
	it('preserves expected zero, false and null values', () => {
		expect(
			parseBenchmarkDataset(
				'[{"prompt":"a","expected":false},{"prompt":"b","expected":0},{"prompt":"c","expected":null}]'
			).map((q) => q.expected)
		).toEqual([false, 0, null]);
	});
	it('preserves zero seeds, validates ranges and separates the seed policy', () => {
		expect(parseInferenceSeeds('0', 'fixed', 3)).toEqual([0]);
		expect(parseInferenceSeeds('0, 1 2', 'list', 3)).toEqual([0, 1, 2]);
		expect(() => parseInferenceSeeds('-1', 'fixed', 1)).toThrow();
		expect(() => parseInferenceSeeds('0,1', 'list', 3)).toThrow();
	});
	it('enforces CPU configurations without changing the supplied values', () => {
		expect(
			parseBenchmarkConfigurations('[{"id":"a","params":{"temperature":0}}]')[0].params
		).toEqual({ temperature: 0, num_gpu: 0 });
		expect(() => parseBenchmarkConfigurations('[{"params":{"num_gpu":1}}]')).toThrow('CPU');
	});
});
