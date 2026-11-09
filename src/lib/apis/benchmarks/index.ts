import { WEBUI_API_BASE_URL } from '$lib/constants';

export interface BenchmarkQuestion {
	id: string;
	prompt: string;
	expected?: unknown;
	metadata?: Record<string, unknown>;
	graph?: { nodes?: string[]; edges: [string, string][]; source: string; target: string };
}

export interface BenchmarkConfiguration {
	id: string;
	name: string;
	params: Record<string, unknown>;
}

export interface BenchmarkModel {
	id: string;
	name: string;
	digest?: string;
	backends: { index: number; name: string }[];
}

export interface BenchmarkScorer {
	type: 'exact' | 'boolean' | 'json_field' | 'graph';
	field?: string;
	trim?: boolean;
	case_sensitive?: boolean;
}

export interface BenchmarkRunRequest {
	name: string;
	model_id: string;
	backend_index: number;
	questions: BenchmarkQuestion[];
	configurations: BenchmarkConfiguration[];
	repeats: number;
	order: 'dataset' | 'reverse' | 'shuffle_once' | 'shuffle_each_repeat';
	order_seed: number;
	seed_mode: 'fixed' | 'list';
	inference_seeds: number[];
	scorer: BenchmarkScorer;
	system_prompt: string;
	timeout_seconds: number;
}

export interface BenchmarkTrial {
	id: string;
	index: number;
	question_id: string;
	configuration_id: string;
	repeat_index: number;
	seed: number;
	status: 'pending' | 'running' | 'completed' | 'error';
	output?: string | null;
	error?: string | null;
	score?: number | boolean | null;
	valid?: boolean | null;
	elapsed_seconds?: number | null;
	device_evidence?: unknown;
	[key: string]: unknown;
}

export interface BenchmarkSummary {
	scored?: number;
	correct?: number;
	accuracy?: number | null;
	errors?: number;
	consistency?: unknown;
	[key: string]: unknown;
}

export interface BenchmarkRun {
	id: string;
	name: string;
	status: 'pending' | 'running' | 'completed' | 'cancelled' | 'failed' | 'interrupted';
	created_at: string | number;
	updated_at: string | number;
	total_trials: number;
	completed_trials: number;
	summary: BenchmarkSummary;
	manifest?: BenchmarkRunRequest & Record<string, unknown>;
	trials?: BenchmarkTrial[];
	error?: string | null;
}

const errorMessage = (body: unknown, status: number): string => {
	if (typeof body === 'object' && body !== null && 'detail' in body) {
		return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
	}
	return typeof body === 'string' && body ? body : `Benchmark request failed (${status})`;
};

async function benchmarkRequest<T>(
	token: string,
	path: string,
	init: RequestInit = {}
): Promise<T> {
	const response = await fetch(`${WEBUI_API_BASE_URL}/benchmarks${path}`, {
		...init,
		headers: {
			Accept: 'application/json',
			Authorization: `Bearer ${token}`,
			...(init.body ? { 'Content-Type': 'application/json' } : {}),
			...init.headers
		}
	});
	const body: unknown = await response.json().catch(() => null);
	if (!response.ok) throw new Error(errorMessage(body, response.status));
	return body as T;
}

export const getBenchmarkModels = (token: string) =>
	benchmarkRequest<{ models: BenchmarkModel[] }>(token, '/models');

export const getBenchmarkRuns = (token: string) =>
	benchmarkRequest<{ runs: BenchmarkRun[] }>(token, '/runs');

export const getBenchmarkRun = (token: string, id: string) =>
	benchmarkRequest<BenchmarkRun>(token, `/runs/${encodeURIComponent(id)}`);

export const createBenchmarkRun = (token: string, request: BenchmarkRunRequest) =>
	benchmarkRequest<BenchmarkRun>(token, '/runs', { method: 'POST', body: JSON.stringify(request) });

export const controlBenchmarkRun = (
	token: string,
	id: string,
	action: 'start' | 'cancel' | 'resume'
) =>
	benchmarkRequest<BenchmarkRun>(token, `/runs/${encodeURIComponent(id)}/${action}`, {
		method: 'POST'
	});

export const exportBenchmarkRun = async (token: string, id: string, format: 'json' | 'csv') => {
	const response = await fetch(
		`${WEBUI_API_BASE_URL}/benchmarks/runs/${encodeURIComponent(id)}/export?format=${format}`,
		{ headers: { Authorization: `Bearer ${token}` } }
	);
	if (!response.ok) {
		throw new Error(errorMessage(await response.json().catch(() => null), response.status));
	}
	return response.blob();
};
