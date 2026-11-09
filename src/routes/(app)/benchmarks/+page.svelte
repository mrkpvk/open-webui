<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { showSidebar, WEBUI_NAME } from '$lib/stores';
	import {
		getBenchmarkModels,
		getBenchmarkRuns,
		getBenchmarkRun,
		createBenchmarkRun,
		controlBenchmarkRun,
		exportBenchmarkRun,
		type BenchmarkModel,
		type BenchmarkRun,
		type BenchmarkRunRequest
	} from '$lib/apis/benchmarks';
	import {
		parseBenchmarkDataset,
		parseBenchmarkConfigurations,
		parseInferenceSeeds,
		graphBenchmarkSample
	} from '$lib/utils/benchmarkDataset';

	let models: BenchmarkModel[] = [];
	let runs: BenchmarkRun[] = [];
	let selected: BenchmarkRun | null = null;
	let modelId = '';
	let backendIndex = 0;
	let name = 'Reachability experiment';
	let dataset = JSON.stringify(graphBenchmarkSample, null, 2);
	let configurations = JSON.stringify(
		[
			{
				id: 'baseline',
				name: 'Greedy CPU',
				params: { temperature: 0, max_tokens: 64, num_ctx: 2048, num_thread: 1 }
			}
		],
		null,
		2
	);
	let repeats = 3;
	let order: BenchmarkRunRequest['order'] = 'dataset';
	let orderSeed = 0;
	let seedMode: 'fixed' | 'list' = 'fixed';
	let seeds = '0';
	let scorer: 'exact' | 'boolean' | 'json_field' | 'graph' = 'graph';
	let field = 'answer';
	let caseSensitive = true;
	let systemPrompt = 'Follow the requested answer format. Give only the answer.';
	let timeoutSeconds = 600;
	let error = '';
	let busy = false;
	let loading = true;
	let view: 'setup' | 'results' = 'setup';
	let poll: ReturnType<typeof setInterval> | undefined;
	let disposed = false;
	let refreshInFlight = false;
	let gridTemperatures = '0, 0.5';
	let gridTopP = '0.9';
	let trialPage = 0;
	const percent = (n: unknown) => (typeof n === 'number' ? `${(n * 100).toFixed(1)}%` : '—');
	const token = () => localStorage.token ?? '';
	$: currentModel = models.find((m) => m.id === modelId);
	$: preview = (() => {
		try {
			const questions = parseBenchmarkDataset(dataset);
			const configs = parseBenchmarkConfigurations(configurations);
			return { questions, configs, total: questions.length * configs.length * repeats, error: '' };
		} catch (e) {
			return { questions: [], configs: [], total: 0, error: String((e as Error).message) };
		}
	})();
	$: summary = selected?.summary;
	$: progress = selected?.total_trials ? selected.completed_trials / selected.total_trials : 0;
	$: repeatMetrics = summary?.consistency as
		{ rate?: number; answer_agreement?: number; groups_with_repeats?: number } | undefined;
	$: configMetrics = (summary?.by_configuration ?? []) as {
		id: string;
		name: string;
		correct: number;
		total: number;
		errors: number;
		accuracy: number;
	}[];
	$: trials = selected?.trials ?? [];
	$: visibleTrials = trials.slice(trialPage * 50, (trialPage + 1) * 50);

	const refresh = async () => {
		if (refreshInFlight || disposed) return;
		refreshInFlight = true;
		try {
			const id = selected?.id;
			const list = await getBenchmarkRuns(token());
			if (disposed) return;
			runs = list.runs;
			if (id) {
				const latest = await getBenchmarkRun(token(), id);
				if (!disposed && selected?.id === id) selected = latest;
			}
		} catch (e) {
			if (!disposed) error = (e as Error).message;
		} finally {
			refreshInFlight = false;
		}
	};

	onMount(async () => {
		try {
			models = (await getBenchmarkModels(token())).models;
			if (models.length) {
				modelId = models[0].id;
				backendIndex = models[0].backends[0]?.index ?? 0;
			}
			await refresh();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
		if (!disposed) poll = setInterval(refresh, 5000);
	});
	onDestroy(() => {
		disposed = true;
		if (poll) clearInterval(poll);
	});

	async function act(action: 'start' | 'cancel' | 'resume') {
		if (!selected || busy) return;
		busy = true;
		error = '';
		try {
			selected = await controlBenchmarkRun(token(), selected.id, action);
			await refresh();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function create() {
		busy = true;
		error = '';
		try {
			if (!Number.isInteger(repeats) || repeats < 1 || preview.total > 5000)
				throw new Error('Choose positive repeats with at most 5,000 total trials.');
			const request: BenchmarkRunRequest = {
				name,
				model_id: modelId,
				backend_index: Number(backendIndex),
				questions: parseBenchmarkDataset(dataset),
				configurations: parseBenchmarkConfigurations(configurations),
				repeats,
				order,
				order_seed: orderSeed,
				seed_mode: seedMode,
				inference_seeds: parseInferenceSeeds(seeds, seedMode, repeats),
				scorer: {
					type: scorer,
					...(scorer === 'json_field' ? { field } : {}),
					...(scorer === 'exact' ? { trim: true, case_sensitive: caseSensitive } : {})
				},
				system_prompt: systemPrompt,
				timeout_seconds: timeoutSeconds
			};
			selected = await createBenchmarkRun(token(), request);
			trialPage = 0;
			view = 'results';
			await refresh();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function openRun(id: string) {
		error = '';
		busy = true;
		try {
			selected = await getBenchmarkRun(token(), id);
			trialPage = 0;
			view = 'results';
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function download(format: 'json' | 'csv') {
		if (!selected) return;
		try {
			const blob = await exportBenchmarkRun(token(), selected.id, format);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `benchmark-${selected.id}.${format}`;
			a.click();
			setTimeout(() => URL.revokeObjectURL(url), 1000);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function importFile(event: Event) {
		const file = (event.target as HTMLInputElement).files?.[0];
		if (!file) return;
		try {
			if (file.size > 2_000_000) throw new Error('Dataset file must be smaller than 2 MB.');
			dataset = JSON.stringify(parseBenchmarkDataset(await file.text()), null, 2);
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function grid() {
		try {
			const values = (text: string) =>
				text.split(',').map((v) => {
					const number = Number(v.trim());
					if (!v.trim() || !Number.isFinite(number))
						throw new Error('Grid values must be comma-separated numbers.');
					return number;
				});
			const temps = values(gridTemperatures),
				tops = values(gridTopP);
			if (temps.length * tops.length > 16) throw new Error('Use at most 16 configurations.');
			configurations = JSON.stringify(
				temps.flatMap((temperature, i) =>
					tops.map((top_p, j) => ({
						id: `t${i}-p${j}`,
						name: `T ${temperature} / top-p ${top_p}`,
						params: { temperature, top_p, max_tokens: 64, num_thread: 1, num_ctx: 2048 }
					}))
				),
				null,
				2
			);
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
	}
</script>

<svelte:head><title>Benchmarks • {$WEBUI_NAME}</title></svelte:head>

<div
	class="benchmark-page w-full h-screen overflow-y-auto {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<header
		class="sticky top-0 z-10 bg-white/95 dark:bg-gray-900/95 border-b border-gray-200 dark:border-gray-800 px-5 py-4 flex justify-between items-center gap-3"
	>
		<div class="flex items-center gap-3">
			<button
				aria-label="Toggle sidebar"
				class="rounded-lg border px-2 py-1 md:hidden"
				on:click={() => showSidebar.set(!$showSidebar)}>☰</button
			>
			<div>
				<h1 class="text-xl font-semibold">Benchmarks</h1>
				<p class="text-xs text-gray-500 mt-0.5">
					Question sets, controlled experiments, inspectable results
				</p>
			</div>
		</div>
		<div class="flex gap-2">
			<button class:active={view === 'setup'} on:click={() => (view = 'setup')}
				>New experiment</button
			><button
				class:active={view === 'results'}
				disabled={!selected}
				on:click={() => (view = 'results')}>Results</button
			>
		</div>
	</header>
	<main class="max-w-6xl mx-auto p-5 md:p-8 space-y-5">
		{#if error}<div
				role="alert"
				class="rounded-xl bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200 p-4 text-sm"
			>
				{error}
			</div>{/if}
		{#if loading}<p role="status">Loading benchmark models and saved experiments…</p>{/if}
		{#if view === 'setup'}
			<div
				class="rounded-xl border border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-900 p-4 text-sm"
			>
				<strong>CPU experiments.</strong> Each question gets a fresh context. Runs use one pinned Ollama
				connection, explicit seeds and zero GPU layers. Repeatability is measured for the saved setup.
			</div>
			{#if !loading && !models.length}<div class="panel">
					No eligible Ollama models are available. Start your configured Ollama service and install
					or grant access to a model, then <button on:click={() => location.reload()}>reload</button
					>.
				</div>{/if}
			<section class="panel">
				<h2>1. Dataset</h2>
				<div class="flex flex-wrap gap-2 mb-3">
					<label class="file-label"
						>Import JSON / JSONL / CSV<input
							type="file"
							accept=".json,.jsonl,.csv"
							on:change={importFile}
						/></label
					><button
						on:click={() => {
							dataset = JSON.stringify(graphBenchmarkSample, null, 2);
							scorer = 'graph';
						}}>Load graph example</button
					>
				</div>
				<label
					>Question set<textarea
						aria-label="Question set"
						class="font-mono text-xs"
						rows="10"
						bind:value={dataset}
					></textarea></label
				>
				<p class="hint">
					Fields: id, prompt, expected. Graph scoring also uses graph.nodes, edges, source and
					target. JSON objects may contain a questions array.
				</p>
				{#if preview.error}<p class="text-red-600 text-sm mt-2">{preview.error}</p>{:else}<p
						class="hint"
					>
						{preview.questions.length} questions validated. Dataset contents are saved with each experiment.
					</p>{/if}
			</section>
			<section class="panel">
				<h2>2. Model and configurations</h2>
				<div class="grid md:grid-cols-3 gap-4">
					<label>Experiment name<input bind:value={name} maxlength="160" /></label>
					<label
						>Model<select
							bind:value={modelId}
							on:change={() => {
								backendIndex = models.find((m) => m.id === modelId)?.backends[0]?.index ?? 0;
							}}
							>{#each models as model}<option value={model.id}>{model.name}</option>{/each}</select
						></label
					>
					<label
						>Ollama connection<select bind:value={backendIndex}
							>{#each currentModel?.backends ?? [] as backend}<option value={backend.index}
									>{backend.name}</option
								>{/each}</select
						></label
					>
				</div>
				<details class="mt-4">
					<summary class="cursor-pointer text-sm font-medium">Build a parameter grid</summary>
					<div class="grid md:grid-cols-3 gap-3 mt-3">
						<label>Temperatures<input bind:value={gridTemperatures} /></label><label
							>Top-p values<input bind:value={gridTopP} /></label
						><button class="self-end" on:click={grid}>Generate configurations</button>
					</div>
				</details>
				<label class="mt-4"
					>Named configurations<textarea
						aria-label="Named configurations"
						class="font-mono text-xs"
						rows="8"
						bind:value={configurations}
					></textarea></label
				>
				<p class="hint">
					Edit sampling, max_tokens, num_ctx or num_thread for each configuration. GPU layers are
					fixed at zero. Set inference seeds below.
				</p>
			</section>
			<section class="panel">
				<h2>3. Repeats, ordering and scoring</h2>
				<div class="grid md:grid-cols-3 gap-4">
					<label
						>Repeats per question<input
							type="number"
							min="1"
							max="100"
							bind:value={repeats}
						/></label
					>
					<label
						>Question order<select bind:value={order}
							><option value="dataset">Dataset order</option><option value="reverse"
								>Reverse order</option
							><option value="shuffle_once">Shuffle once</option><option value="shuffle_each_repeat"
								>Shuffle each repeat</option
							></select
						></label
					>
					<label
						>Ordering seed<input
							type="number"
							min="0"
							max="2147483647"
							bind:value={orderSeed}
						/></label
					>
					<label
						>Inference seed policy<select bind:value={seedMode}
							><option value="fixed">Same seed every repeat</option><option value="list"
								>One seed per repeat</option
							></select
						></label
					>
					<label>Inference seed(s)<input bind:value={seeds} /></label>
					<label
						>Timeout per request (seconds)<input
							type="number"
							min="5"
							max="3600"
							bind:value={timeoutSeconds}
						/></label
					>
					<label
						>Automatic scorer<select bind:value={scorer}
							><option value="exact">Exact text</option><option value="boolean"
								>Boolean answer</option
							><option value="json_field">JSON field</option><option value="graph"
								>Directed reachability oracle</option
							></select
						></label
					>
					{#if scorer === 'json_field'}<label
							>JSON field path<input bind:value={field} placeholder="answer" /></label
						>{/if}
					{#if scorer === 'exact'}<label class="flex items-center gap-2"
							><input type="checkbox" bind:checked={caseSensitive} />Case sensitive (outer
							whitespace trimmed)</label
						>{/if}
				</div>
				<label class="mt-4"
					>System instruction<textarea rows="2" bind:value={systemPrompt}></textarea></label
				>
				<p class="hint">
					Boolean and graph answers must contain only true/false, yes/no or 1/0. Graph reachability
					includes a zero-edge path from a node to itself. No LLM judge is used.
				</p>
			</section>
			<div class="panel flex flex-wrap items-center justify-between gap-4">
				<div>
					<strong class="text-lg">{preview.total.toLocaleString()} scored requests</strong>
					<p class="hint">
						{preview.questions.length} questions × {preview.configs.length} configurations × {repeats}
						repeats. Limit: 5,000.
					</p>
				</div>
				<button
					class="primary"
					disabled={busy || !modelId || !!preview.error || !preview.total || preview.total > 5000}
					on:click={create}>{busy ? 'Saving…' : 'Save experiment'}</button
				>
			</div>
		{:else if selected}
			<section class="panel">
				<div class="flex flex-wrap items-center justify-between gap-3">
					<div>
						<h2 class="mb-1">{selected.name}</h2>
						<p class="hint">{selected.manifest?.model_id} · CPU · {selected.status}</p>
					</div>
					<div class="flex flex-wrap gap-2">
						{#if selected.status === 'running'}<button
								disabled={busy}
								on:click={() => act('cancel')}>Cancel run</button
							>{:else if selected.status !== 'completed'}<button
								class="primary"
								disabled={busy}
								on:click={() => act(selected?.status === 'pending' ? 'start' : 'resume')}
								>{selected.status === 'pending' ? 'Start run' : 'Resume unfinished trials'}</button
							>{/if}
						<button on:click={() => download('json')}>Export JSON</button><button
							on:click={() => download('csv')}>Export CSV</button
						>
					</div>
				</div>
				<progress class="w-full mt-4" max="1" value={progress}></progress>
				<p class="hint">
					{selected.completed_trials} / {selected.total_trials} trials finished. You can close this page;
					results are checkpointed by the server.
				</p>
				{#if selected.error}<p class="text-sm text-amber-700 mt-2">{selected.error}</p>{/if}
			</section>
			<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
				<div class="panel">
					<p class="hint">Accuracy / scheduled</p>
					<strong class="metric">{percent(summary?.accuracy)}</strong>
				</div>
				<div class="panel">
					<p class="hint">Valid answers / finished</p>
					<strong class="metric">{percent(summary?.valid_rate)}</strong>
				</div>
				<div class="panel">
					<p class="hint">Answer agreement</p>
					<strong class="metric">{percent(repeatMetrics?.answer_agreement)}</strong>
				</div>
				<div class="panel">
					<p class="hint">Exact output identity</p>
					<strong class="metric">{percent(repeatMetrics?.rate)}</strong>
				</div>
			</div>
			<p class="hint">
				Pending and error trials stay in scheduled accuracy's denominator. Agreement compares groups
				with at least two comparable outputs; inspect coverage and raw responses. A consistent
				answer can still be wrong.
			</p>
			<section class="panel overflow-x-auto">
				<h2>Configuration comparison</h2>
				<table>
					<thead
						><tr
							><th>Configuration</th><th>Correct / scheduled</th><th>Accuracy</th><th
								>Request errors</th
							></tr
						></thead
					><tbody
						>{#each configMetrics as config}<tr
								><td>{config.name}</td><td>{config.correct} / {config.total}</td><td
									>{percent(config.accuracy)}</td
								><td>{config.errors}</td></tr
							>{/each}</tbody
					>
				</table>
			</section>
			<section class="panel">
				<div class="flex justify-between items-center gap-3 mb-3">
					<h2 class="mb-0">Trial results</h2>
					<div class="flex items-center gap-2">
						<button disabled={trialPage === 0} on:click={() => trialPage--}>Previous</button><span
							class="hint">Page {trialPage + 1} / {Math.max(1, Math.ceil(trials.length / 50))}</span
						><button disabled={(trialPage + 1) * 50 >= trials.length} on:click={() => trialPage++}
							>Next</button
						>
					</div>
				</div>
				<div class="max-h-[36rem] overflow-auto space-y-2">
					{#each visibleTrials as trial}<details class="trial">
							<summary class="cursor-pointer flex flex-wrap gap-x-3 gap-y-1 text-sm"
								><span class="font-mono text-xs">#{trial.index + 1}</span><strong
									>{trial.question_id}</strong
								><span>{trial.configuration_id}</span><span
									>repeat {trial.repeat_index + 1} · seed {trial.seed}</span
								><span class="ml-auto"
									>{trial.status === 'completed'
										? trial.score === 1
											? '✓ Correct'
											: 'Incorrect'
										: trial.status}</span
								></summary
							>
							<p class="hint mt-2">
								{trial.elapsed_seconds ?? '—'} seconds · {String(trial.attempts ?? 0)} attempt(s)
							</p>
							{#if trial.error || trial.scorer_error}<p class="text-red-600 text-sm mt-2">
									{trial.error ?? String(trial.scorer_error)}
								</p>{/if}
							<pre
								class="mt-2 whitespace-pre-wrap text-xs bg-gray-50 dark:bg-gray-950 p-3 rounded-lg">{trial.output ??
									'No response yet.'}</pre>
							<details class="mt-2">
								<summary class="text-xs cursor-pointer">Request, scoring and CPU evidence</summary>
								<pre class="whitespace-pre-wrap text-xs mt-2">{JSON.stringify(trial, null, 2)}</pre>
							</details>
						</details>{/each}
				</div>
			</section>
			<details class="panel">
				<summary class="cursor-pointer font-medium">Frozen experiment manifest</summary>
				<pre class="text-xs whitespace-pre-wrap mt-3 max-h-96 overflow-auto">{JSON.stringify(
						selected.manifest,
						null,
						2
					)}</pre>
			</details>
		{/if}
		<section class="panel">
			<div class="flex justify-between items-center">
				<h2>Saved experiments</h2>
				<button on:click={refresh}>Refresh</button>
			</div>
			{#if !runs.length}<p class="hint">Your saved experiments will appear here.</p>{:else}<div
					class="space-y-2"
				>
					{#each runs as run}<button
							class="saved-run w-full flex justify-between gap-3 text-left"
							disabled={busy}
							on:click={() => openRun(run.id)}
							><span>{run.name}</span><span class="text-xs text-gray-500"
								>{run.status} · {run.completed_trials}/{run.total_trials}</span
							></button
						>{/each}
				</div>{/if}
		</section>
	</main>
</div>

<style>
	.benchmark-page {
		background: var(--color-gray-50, #fafafa);
	}
	:global(.dark) .benchmark-page {
		background: #111827;
	}
	.panel {
		border: 1px solid #e5e7eb;
		border-radius: 1rem;
		padding: 1.25rem;
		background: white;
	}
	:global(.dark) .panel {
		border-color: #374151;
		background: #171f2f;
	}
	h2 {
		font-size: 1rem;
		font-weight: 650;
		margin-bottom: 1rem;
	}
	label {
		display: block;
		font-size: 0.8rem;
		font-weight: 550;
	}
	input:not([type='checkbox']):not([type='file']),
	select,
	textarea {
		display: block;
		width: 100%;
		border: 1px solid #cbd5e1;
		border-radius: 0.6rem;
		padding: 0.6rem 0.7rem;
		margin-top: 0.4rem;
		background: transparent;
		font-weight: 400;
	}
	input[type='checkbox'] {
		width: 1rem;
	}
	button,
	.file-label {
		border: 1px solid #cbd5e1;
		border-radius: 0.6rem;
		padding: 0.55rem 0.8rem;
		font-size: 0.8rem;
		font-weight: 550;
		cursor: pointer;
	}
	button:hover,
	.file-label:hover {
		background: #e5e7eb55;
	}
	button:disabled {
		opacity: 0.45;
		cursor: default;
	}
	button.primary,
	button.active {
		background: #2563eb;
		color: white;
		border-color: #2563eb;
	}
	.file-label input {
		display: none;
	}
	.hint {
		font-size: 0.75rem;
		color: #64748b;
		margin-top: 0.4rem;
		font-weight: 400;
	}
	:global(.dark) .hint {
		color: #9ca3af;
	}
	.metric {
		font-size: 1.7rem;
		display: block;
		margin-top: 0.5rem;
	}
	table {
		width: 100%;
		font-size: 0.8rem;
		border-collapse: collapse;
	}
	th,
	td {
		text-align: left;
		padding: 0.7rem;
		border-bottom: 1px solid #e5e7eb44;
	}
	.trial {
		border: 1px solid #94a3b844;
		border-radius: 0.6rem;
		padding: 0.8rem;
	}
	progress {
		accent-color: #2563eb;
		height: 0.6rem;
	}
</style>
