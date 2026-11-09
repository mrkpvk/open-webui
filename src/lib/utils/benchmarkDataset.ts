import type { BenchmarkConfiguration, BenchmarkQuestion } from '../apis/benchmarks';

/** RFC 4180-style CSV parsing, including quoted commas, escaped quotes and newlines. */
export const parseBenchmarkCsv = (text: string): string[][] => {
	const rows: string[][] = [];
	let row: string[] = [];
	let field = '';
	let quoted = false;
	for (let i = 0; i < text.length; i++) {
		const character = text[i];
		if (character === '"') {
			if (quoted && text[i + 1] === '"') {
				field += '"';
				i++;
			} else if (!field || quoted) quoted = !quoted;
			else throw new Error('CSV quote must begin at the start of a field.');
		} else if (character === ',' && !quoted) {
			row.push(field);
			field = '';
		} else if ((character === '\n' || character === '\r') && !quoted) {
			if (character === '\r' && text[i + 1] === '\n') i++;
			row.push(field);
			if (row.some((value) => value.trim())) rows.push(row);
			row = [];
			field = '';
		} else field += character;
	}
	if (quoted) throw new Error('CSV contains an unclosed quoted field.');
	row.push(field);
	if (row.some((value) => value.trim())) rows.push(row);
	return rows;
};

const parseCell = (cell: string): unknown => {
	try {
		return JSON.parse(cell);
	} catch {
		return cell;
	}
};

const record = (value: unknown): value is Record<string, unknown> =>
	typeof value === 'object' && value !== null && !Array.isArray(value);

export const parseBenchmarkDataset = (
	input: string,
	format: 'auto' | 'json' | 'jsonl' | 'csv' = 'auto'
): BenchmarkQuestion[] => {
	const text = input.replace(/^\uFEFF/, '').trim();
	if (!text) throw new Error('Add at least one question.');
	let parsed: unknown;
	const selected =
		format === 'auto'
			? text.startsWith('[')
				? 'json'
				: text.startsWith('{')
					? 'jsonl'
					: 'csv'
			: format;
	if (selected === 'csv') {
		const rows = parseBenchmarkCsv(text);
		const header = rows.shift()?.map((cell) => cell.trim().toLowerCase()) ?? [];
		if (!header.includes('prompt'))
			throw new Error(
				'CSV needs a prompt column. Optional columns: id, expected, metadata, graph.'
			);
		parsed = rows.map((row, index) => {
			if (row.length !== header.length)
				throw new Error(
					`CSV row ${index + 2} has ${row.length} fields; expected ${header.length}.`
				);
			return Object.fromEntries(
				header.map((key, i) => [
					key,
					['expected', 'metadata', 'graph'].includes(key) ? parseCell(row[i]) : row[i]
				])
			);
		});
	} else {
		try {
			parsed = JSON.parse(text);
		} catch (error) {
			if (selected === 'json') throw new Error('Dataset is not valid JSON.');
			parsed = text
				.split(/\r?\n/)
				.filter((line) => line.trim())
				.map((line, index) => {
					try {
						return JSON.parse(line);
					} catch {
						throw new Error(`JSONL line ${index + 1} is not valid JSON.`);
					}
				});
		}
		if (record(parsed) && Array.isArray(parsed.questions)) parsed = parsed.questions;
		else if (record(parsed) && 'prompt' in parsed) parsed = [parsed];
	}
	if (!Array.isArray(parsed) || !parsed.length)
		throw new Error('Dataset must contain a nonempty array of questions.');
	const ids = new Set<string>();
	return parsed.map((value, index) => {
		if (!record(value) || typeof value.prompt !== 'string' || !value.prompt.trim())
			throw new Error(`Question ${index + 1} needs a nonempty prompt.`);
		const id = String(value.id ?? `q${index + 1}`).trim();
		if (!id || ids.has(id))
			throw new Error(`Question ${index + 1} has an empty or duplicate id: ${id}.`);
		ids.add(id);
		if (value.metadata != null && !record(value.metadata))
			throw new Error(`Question ${id}: metadata must be a JSON object.`);
		if (value.graph != null && !record(value.graph))
			throw new Error(`Question ${id}: graph must be a JSON object.`);
		return { ...value, id, prompt: value.prompt } as BenchmarkQuestion;
	});
};

export const parseBenchmarkConfigurations = (text: string): BenchmarkConfiguration[] => {
	let parsed: unknown;
	try {
		parsed = JSON.parse(text);
	} catch {
		throw new Error('Configurations must be valid JSON.');
	}
	if (!Array.isArray(parsed) || !parsed.length) throw new Error('Add at least one configuration.');
	const ids = new Set<string>();
	return parsed.map((value, index) => {
		if (!record(value) || !record(value.params))
			throw new Error(`Configuration ${index + 1} needs a params object.`);
		const id = String(value.id ?? `config-${index + 1}`);
		if (!id.trim() || ids.has(id))
			throw new Error('Configuration ids must be nonempty and unique.');
		ids.add(id);
		if ('num_gpu' in value.params && value.params.num_gpu !== 0)
			throw new Error(`Configuration ${id}: CPU benchmarking requires num_gpu: 0.`);
		return {
			id,
			name: typeof value.name === 'string' ? value.name : id,
			params: { ...value.params, num_gpu: 0 }
		};
	});
};

export const parseInferenceSeeds = (
	text: string,
	mode: 'fixed' | 'list',
	repeats: number
): number[] => {
	const values = text
		.split(/[\s,]+/)
		.filter(Boolean)
		.map((value) => {
			if (
				!/^\d+$/.test(value) ||
				!Number.isSafeInteger(Number(value)) ||
				Number(value) > 2147483647
			)
				throw new Error(
					'Seeds must be integers from 0 to 2147483647, separated by commas or spaces.'
				);
			return Number(value);
		});
	if (mode === 'fixed' && values.length !== 1)
		throw new Error('Fixed seed mode needs exactly one seed.');
	if (mode === 'list' && values.length !== repeats)
		throw new Error(`Provide exactly ${repeats} seeds, one for each repeat.`);
	return values;
};

export const graphBenchmarkSample: BenchmarkQuestion[] = [
	{
		id: 'reachable',
		prompt: 'Directed edges: A → B, B → C. Is C reachable from A? Answer only true or false.',
		expected: true,
		graph: {
			nodes: ['A', 'B', 'C'],
			edges: [
				['A', 'B'],
				['B', 'C']
			],
			source: 'A',
			target: 'C'
		}
	},
	{
		id: 'reverse',
		prompt: 'Directed edges: A → B, B → C. Is A reachable from C? Answer only true or false.',
		expected: false,
		graph: {
			nodes: ['A', 'B', 'C'],
			edges: [
				['A', 'B'],
				['B', 'C']
			],
			source: 'C',
			target: 'A'
		}
	},
	{
		id: 'disconnected',
		prompt: 'Directed edges: A → B, C → D. Is D reachable from A? Answer only true or false.',
		expected: false,
		graph: {
			nodes: ['A', 'B', 'C', 'D'],
			edges: [
				['A', 'B'],
				['C', 'D']
			],
			source: 'A',
			target: 'D'
		}
	}
];
