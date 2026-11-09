# Benchmarks mode

Open **Benchmarks** from the sidebar, or visit `/benchmarks` while signed in. Ordinary chats remain available. This first implementation supports installed direct Ollama models on an eligible configured connection and runs inference on CPU. Models with WebUI parameter/system presets or chained base-model definitions are excluded so experiments cannot bypass those configured policies; use a plain research model entry with the appropriate access grants.

## Run an experiment

1. Load the graph example, paste questions, or import a `.json`, `.jsonl` or `.csv` file. Preview validation catches missing prompts and duplicate IDs. The backend also validates the scoring ground truth.
2. Select an available model and its Ollama connection. Give the experiment a name. Edit named JSON configurations, or generate a grid of temperatures and top-p values.
3. Choose repeats, question order, ordering seed, inference seed policy, timeout, system instruction and scorer. Review the total request count.
4. **Save experiment** freezes the dataset, expanded schedule, options, model digest and runtime information. Inspect the saved manifest, then **Start run**.
5. Follow progress and inspect individual responses. Export JSON for the complete experiment or CSV for a trial table. Saved experiments remain after closing the browser or restarting the app.

The limits are 500 questions, 16 configurations, 100 repeats and 5,000 scheduled trials per experiment; inputs are capped at 2 MB. One benchmark can run at a time across workers sharing this local data directory. CPU experiments can take substantial time, so use a small pilot first.

## Dataset format

JSON is an array of questions or an object containing a `questions` array. JSONL contains one question object per line. CSV uses `id,prompt,expected`, with optional `metadata` and `graph` columns containing JSON. Quoted CSV supports commas, quotes and multiline prompts. IDs may be generated on import when omitted; the saved version always contains explicit IDs.

```json
[
	{
		"id": "capital",
		"prompt": "What is the capital of France? Reply with one word.",
		"expected": "Paris"
	},
	{ "id": "arithmetic", "prompt": "What is 2 + 2? Reply with the number only.", "expected": "4" }
]
```

Use strings for exact scoring. CSV expected values are parsed as JSON when possible: for exact numeric text use a JSON string inside the CSV field (see the quoted `4` in the CSV example), or use a JSON dataset. Boolean and JSON-field scoring can use boolean, number, null, list or object values as appropriate. Metadata such as `graph_id`, `encoding_id` or experimental condition is retained in the frozen dataset and JSON export.

## Scorers

| Scorer         | Behavior                                                                                                                                                                                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Exact text     | Compares the full response after trimming outer whitespace. Case sensitivity is configurable. An incorrect string is a valid but wrong answer.                                                                                                                      |
| Boolean        | Requires a single `true`, `false`, `yes`, `no`, `1` or `0` token, ignoring case and outer whitespace. Explanations or conflicting answers are invalid.                                                                                                              |
| JSON field     | Parses the entire response as strict JSON and compares the selected dotted field path, including array indices such as `results.0.answer`. Booleans are distinct from numbers. Code fences and missing fields are invalid.                                          |
| Directed graph | Computes ground truth with a conventional directed reachability search from `question.graph`. Requires a boolean-style model answer. A source node is reachable from itself by a zero-edge path. A supplied `expected` label is superseded by computed graph truth. |

Graph questions include this structure:

```json
{
	"id": "path",
	"prompt": "Directed edges: A -> B, B -> C. Is C reachable from A? Answer only true or false.",
	"graph": {
		"nodes": ["A", "B", "C"],
		"edges": [
			["A", "B"],
			["B", "C"]
		],
		"source": "A",
		"target": "C"
	}
}
```

No uploaded scoring code or model judge is executed. The scorer version is recorded. Results preserve the raw response, parsed answer, expected answer and parsing error.

## Parameters, ordering and repeats

Configurations have `id`, `name` and `params`. The server resolves explicit options before saving. Supported controls include temperature, top-p/top-k/min-p/typical-p, repeat/presence/frequency penalties, stop sequences, generated-token limit (`max_tokens` or `num_predict`), context size, CPU threads and batch size. Unsupported parameters are rejected. Use a literal string array for stop sequences. GPU layers are always zero; attempts to request another value fail validation. Inference seeds are set separately.

Dataset, reversed, shuffle-once and shuffle-per-repeat ordering are available. Each repeat uses the same question order across configurations. Execution proceeds repeat → question → configuration, with one inference request at a time. The fully expanded schedule is saved. The ordering seed never consumes or changes inference seeds. Fixed seed mode uses one integer for all repeats; list mode requires exactly one integer per repeat. Zero is valid.

Every question gets a fresh message context consisting of the frozen system instruction and that question. Previous questions and normal chat settings are not inserted. There is no response-result cache. The inference engine's prefix/KV cache remains an engine feature and is recorded as the engine default. Avoid simultaneous chat or other Ollama workloads when measuring controlled latency or repeatability.

## Results and reproducibility

- **Accuracy / scheduled:** correct answers divided by every scheduled trial. Pending, invalid and transport-error trials cannot inflate it. Inspect coverage for unfinished runs.
- **Validity / finished:** parse-valid completed outputs divided by finished trials, including transport errors in the denominator.
- **Answer agreement:** fraction of question/configuration groups with at least two valid parsed answers whose comparable answers all agree.
- **Exact output identity:** fraction of groups with at least two completed outputs whose raw answer text and any separately returned thinking text are identical. Timing and provider timestamps are excluded from this identity. This is distinct from answer agreement and correctness. Inspect group counts and coverage in the JSON summary.

The manifest retains dataset hash, explicit schedule, effective options, seed policies, model digest/template/parameters, Ollama version and app build/source information when available. Each successful trial includes its exact request, complete provider response, answer and generation hashes, any returned thinking text, usage, elapsed time and loaded-model telemetry with `size_vram=0`. Missing or nonzero VRAM telemetry produces an explicit trial error. Model/backend identity and Ollama version are rechecked during execution; changed environments require a new experiment. Credentials and raw connection URLs are excluded from the manifest.

CPU support and fixed seeds do not establish universal determinism. Repeatability is measured under the saved environment. This mode currently covers independent, text-only questions; cloud providers, shared-conversation experiments, warm-up controls, automatic statistical intervals and paired encoding analysis are future extensions. Export metadata and per-question results for further analysis.

JSON preserves full raw outputs and provenance. CSV includes every scheduled trial, including pending and error rows. Spreadsheet formula-like cell values are prefixed with an apostrophe for safe viewing; use JSON when byte-exact output text matters.

## Cancellation, restart and storage

Cancellation stops the app worker and preserves completed checkpoints. Resume retries incomplete trials and retains their attempt history; already finished trials and error records are preserved. Cancellation of an active inference is best effort at the provider, so the engine may take a short time to stop. There is no automatic rerun of finished errors.

A SQLite lease prevents competing benchmark workers using the same data directory. After an abrupt process exit, opening the run recovers an expired lease (up to 60 seconds) as **interrupted**. Choose **Resume unfinished trials** to continue. Closing a browser tab does not cancel the backend task. Use one shared local filesystem/data directory for a multi-worker instance; independent replicas with different data directories are separate runners.

Benchmark state is stored in `DATA_DIR/benchmarks.sqlite3`, separate from the chat database. Back up this database with its WAL using a SQLite-aware backup or while the app is stopped. Dataset imports do not modify chat history or model definitions.

## Rollback

The [pre-benchmark backup branch](https://github.com/mrkpvk/open-webui/tree/backup/pre-benchmarks-2026-11-09) points to tested checkpoint `527250fa9283e29056ab63aadb082eb066525312`. The [original fork backup](https://github.com/mrkpvk/open-webui/tree/backup/pre-review-2026-11-09) preserves the earlier GitHub version. These references are published on the user's fork.

To inspect the previous version in another local branch:

```powershell
git fetch origin
git switch -c rollback/pre-benchmarks origin/backup/pre-benchmarks-2026-11-09
```

Commit or otherwise preserve unfinished work before switching. To roll back the fork's default branch, make a new commit restoring the backup version, or revert subsequent integration commits followed by the benchmark feature commit. No force push is needed. Older code ignores the separate benchmark database. Keep it for later recovery.
