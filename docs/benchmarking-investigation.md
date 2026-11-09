# Benchmarking mode: investigation and implementation brief

Investigated 9 November 2026. This document preserves the original design proposal. A native CPU benchmark mode was subsequently implemented and tested; see [the implementation and usage guide](benchmarking.md) for delivered behavior and remaining extensions. This research brief includes ideas beyond the current implementation.

## Recommendation

Add a separate **Benchmarks** workspace with four views: **Datasets → Experiment setup → Run progress → Results**. Keep ordinary chats available. Build a small durable runner behind it, borrowing the established dataset/experiment/result model rather than automating the chat screen. Retain CPU inference as a first-class requirement. The initial focus should be trusted-answer question sets, repeatability and parameter comparisons, including the EPQ's information-equivalent encodings of directed graphs.

For a quick external reference implementation, Inspect AI fits the research workflow particularly well. Promptfoo offers a useful model for a comparison interface. Integrating an entire evaluation framework into Open WebUI is an option to prototype separately, not a prerequisite for the first native mode.

## What established tools do

| Tool                                 | Observed approach                                                                                                                                                                                                                                                      | What to adopt here                                                                                                                                                                                                                                                                                                                    |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Promptfoo                            | Configurations combine prompts, providers and test cases with assertions; generation options can differ between cases. The runner exposes repeat count, concurrency, timeouts and caching, with JSON/JSONL/CSV and other exports.                                      | Show the complete experiment matrix and predicted request count before execution; retain each output and assertion result. [Configuration reference](https://www.promptfoo.dev/docs/configuration/reference/)                                                                                                                         |
| LangSmith                            | Dataset examples are evaluated in experiments. Repetitions rerun the target and evaluators; concurrency is configurable. Its interface exposes repeated outputs, average scores and variability.                                                                       | Store repetitions individually and allow drilling down from aggregate scores to exact responses. [Experiment configuration](https://docs.langchain.com/langsmith/experiment-configuration), [Repetitions](https://docs.langchain.com/langsmith/repetition)                                                                            |
| Inspect AI, UK AI Security Institute | Explicit datasets, solvers and scorers; epochs repeat samples, with configurable aggregation. Datasets support seeded shuffling. Eval sets support parameter/model comparisons and recovery of completed work. Logs retain sample inputs, outputs, targets and scores. | Adopt stable question IDs, explicit ordering and a saved run manifest; make interrupted CPU runs recoverable. [Datasets](https://inspect.aisi.org.uk/datasets.html), [Options](https://inspect.aisi.org.uk/options.html), [Eval sets](https://inspect.aisi.org.uk/eval-sets.html), [Logs](https://inspect.aisi.org.uk/eval-logs.html) |
| EleutherAI LM Evaluation Harness     | Reusable task definitions, explicit generation arguments, device/batch settings, seeds and sample-level output logging. CPU is an available device for supported local model implementations.                                                                          | Record the exact setup and raw samples; separate model inference seeds from dataset sampling seeds. [CLI interface](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md)                                                                                                                                  |

These are observations from public primary documentation, not a claim that the companies use the same internal benchmarking infrastructure. The design below is a recommendation for this fork.

## CPU inference and the nondeterminism paper

The likely reference is **Horace He and Thinking Machines Lab, “Defeating Nondeterminism in LLM Inference,” 10 September 2025**, from Mira Murati's company. The credited author is Horace He with collaborators. The article distinguishes random token sampling from numerical variation, especially batch-size-dependent computation. It explicitly says CPU and TPU endpoints can also exhibit this source of nondeterminism; its remedy concerns batch-invariant computation. Temperature zero and a fixed seed therefore do not, by themselves, establish a deterministic system. [Original article](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)

Keep CPU as the intended execution path and **measure** reproducibility on that path. Do not silently switch to GPU for speed. A CPU preset should submit `num_gpu: 0` to a compatible local Ollama backend, keep explicit zero-valued parameters, pin the backend and model digest, and save the effective request. Confirm support in the installed Ollama version. Inspect loaded-model telemetry, including `size_vram`, and server process/log information rather than treating a UI setting as proof of execution hardware. Ollama's process endpoint exposes digest, quantization and VRAM fields. [Ollama running models API](https://docs.ollama.com/api/ps)

Suggested first reproducibility check: one pinned model, one fixed prompt, fixed sampling settings, sequential fresh requests, no response-result cache, repeated both within one server session and after a controlled restart. Save full outputs and hashes. Passing establishes observed repeatability under the recorded conditions, not a universal guarantee across machines or runtime updates. Keep warm-up requests outside scored results and record whether the model remained loaded.

## Minimum useful experiment setup

| Area       | Proposed behavior                                                                                                                                                                                                                                |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Dataset    | Import JSON/JSONL first; add CSV as a convenience. Require stable unique `question_id`, exact input, expected answer, and optional metadata. Preview validation errors before saving a version.                                                  |
| Model      | Select one local Ollama model initially. Capture server version, model name **and digest**, quantization, template/system prompt and endpoint identity. A mutable model tag alone is insufficient provenance.                                    |
| Parameters | Choose named configurations or an explicit grid of values: seed, temperature, top-p/top-k, max generated tokens, context size, threads and supported sampling options. Display unsupported/ignored options as validation errors for strict runs. |
| Repeats    | Positive integer per question/configuration. Offer “same inference seed each repeat” for repeatability and “explicit seed list” for sampling variation. Keep that choice independent of the ordering seed.                                       |
| Ordering   | Dataset order, reversed order, seeded shuffle once, seeded shuffle per repeat, or a supplied ID list. Save the fully expanded order and the shuffle algorithm version.                                                                           |
| Scheduling | Choose repeat-first (one complete dataset pass per repeat) or question-first (all repeats of a question together). Default to sequential execution with one active inference request for the CPU preset.                                         |
| Context    | Default to a fresh request containing only the frozen system instruction and that question. A separately labelled shared-conversation experiment may test context/order effects later.                                                           |
| Scoring    | Exact string/choice match, strict boolean or JSON field match, and a built-in directed reachability oracle. Retain parsing failures and transport errors separately.                                                                             |
| Lifecycle  | Start, cancel, resume and inspect progress. Persist each completed attempt immediately; closing a browser tab must not lose a multi-hour CPU experiment.                                                                                         |
| Results    | Accuracy, answer validity, repeat agreement, raw-output identity, per-question details and configuration comparisons. Export the manifest, dataset version, all attempts and summary.                                                            |

Question execution order, edge order inside a graph encoding, answer-choice order and message order are different experimental variables. Give them separate names and controls. Running independent questions in a different sequence does not itself put previous questions into the model context. Preserve that distinction in the interface and exports.

For example, 100 question rows × 3 configurations × 5 repetitions is **1,500 scored requests**, plus any separately recorded warm-ups or retries. Show this count and token limits before starting; an estimate of CPU duration should be based on a pilot, not a guessed throughput figure.

## EPQ graph dataset and scoring

Store each canonical directed graph and source/target query independently of its rendered encodings. Each row should include `graph_id`, `query_id`, `encoding_id`, `question_id`, exact rendered prompt, and a boolean reference answer. Encodings of the same graph/query must have identical ground truth and stay grouped for paired comparisons. Decide and record whether reachability includes a zero-edge path when source equals target. Compute labels with a conventional directed BFS/DFS and verify any supplied labels during import.

Use one published answer format, for example a final JSON object `{"reachable": true}`. Score the designated answer only, never a substring such as `yes` found somewhere in an explanation. Conflicting answers, malformed JSON and missing fields need a consistent invalid-answer rule. Keep the raw completion, parsed answer, validity, correctness and scorer version. Reasoning-token or output limits that truncate the final answer must be visible in the result.

Report these separately:

- **Accuracy:** correct answers divided by scheduled scored trials for a completed experiment, with invalid outputs counted incorrect. Also provide completed-trial accuracy and coverage for interrupted runs. Never silently remove errors from the denominator.
- **Validity:** fraction of outputs matching the required answer schema.
- **Answer consistency:** for repeats of the _same exact question/configuration_, report all-repeat agreement and pairwise agreement over valid parsed answers, with valid-pair coverage. A consistently wrong answer is still consistent.
- **Raw-output identity:** proportion of comparable outputs that are byte-identical; this is stricter than matching the final boolean answer.
- **Encoding sensitivity:** paired accuracy differences and answer disagreement across encodings of the same graph/query, using matched configurations and seed schedules.

Do not treat repeated trials or encodings of the same graph as independent new graphs when estimating uncertainty. Keep per-graph results available for paired analysis and, if confidence intervals are added, resample at the independent graph level. Keep development questions separate from the final held-out set. These are proposed methodological controls for the EPQ, not statistics already measured in this project.

Avoid an LLM judge for directed reachability correctness: a deterministic graph oracle is more direct and auditable. Optional model grading belongs later for tasks without exact labels, with the judge model and rubric version recorded.

## Provenance, cache and failure rules

Freeze an immutable manifest when a run starts: dataset content hash, prompt/template text, fully resolved parameters, requested and observed device information, backend/model identity, local app commit, dirty-state indicator, scorer version, explicit schedule, both seed policies and environment details. Retain the effective request after defaults and model overrides, excluding credentials. A replay should reproduce the recorded inputs even if ordinary chat settings have since changed.

Disable response-result reuse for any study of inference variability. Promptfoo explicitly distinguishes repeats from forcing fresh provider calls, and LangSmith documents result caching. Reusing an old output can produce misleading apparent stability. Prefix/KV caching is a separate engine feature: record its policy where exposed rather than confusing it with saved-response reuse. [Promptfoo test cases](https://www.promptfoo.dev/docs/configuration/test-cases/), [LangSmith caching](https://docs.langchain.com/langsmith/experiment-configuration)

Assign every scheduled trial a stable key `(run_id, configuration_id, question_id, repeat_index)`. Store retries as additional attempts linked to that key. Resume missing work; do not overwrite earlier outputs or turn retries into unlabelled extra repeats. Save timeout, cancellation, refusal and provider errors explicitly. Display coverage and failure counts alongside scores. Maintain a separate export-friendly score revision if rescoring saved outputs with a newer scorer.

## Where this fits in this fork

The following are local code observations, not upstream API promises:

- `src/routes/(app)/playground/+layout.svelte` already separates chat, completion and image tools. A top-level `/benchmarks` route is a cleaner distinct mode; a link can also appear from Playground.
- `backend/open_webui/routers/evaluations.py` manages human feedback, arena configuration and an Elo-style leaderboard. It is not a question-set execution engine. Keep the new runner separate from those tables and routes.
- `backend/open_webui/main.py`'s chat endpoint merges global/model parameters and handles chat metadata. A benchmark must freeze the resolved defaults instead of inheriting future settings changes.
- `backend/open_webui/routers/ollama.py` already contains verified-user/model access checks and backend routing. Reuse these access rules. Its automatic backend choice can select among model URLs, so strict experiments need an explicitly pinned eligible backend rather than unrecorded load distribution.
- `backend/open_webui/utils/payload.py` maps generation options. Share the validated provider conversion layer and capture the final options sent to the engine. A repetition warning in a rendered chat message is not an enforced decoding constraint and must not be scored as one.
- `src/lib/components/chat/RawContextEditor.svelte` is a useful prompt-inspection concept. Benchmark previews should be derived from the frozen manifest and show exact messages and effective settings.

Proposed persistence entities: dataset versions, configurations, runs, scheduled trials and attempts. Proposed API surface: authenticated dataset import/preview, create run, fetch run/progress/results, cancel, resume, and export. Enforce owner access with the existing user/model permissions; a worker must not acquire broader model privileges than the initiating user. Keep imported scoring declarative at first rather than executing uploaded Python/JavaScript.

The runner should be owned by the backend, with durable checkpoints and a single-worker implementation first. A background task must be tested against process restarts and multi-worker deployments; do not rely solely on browser state or an untracked in-process loop. No GPU inference requirement or additional cloud service is needed for this design.

## Delivery stages and acceptance checks

1. **Protocol and fixtures:** commit a versioned manifest/dataset schema; validate duplicate IDs, finite parameters, zero-valued seeds, unsupported options and an explicitly bounded experiment size. Add small directed graphs with cycles, disconnected vertices and source-equals-target cases. Preview the exact expanded schedule and prompt.
2. **CPU vertical slice:** one pinned Ollama backend/model, one dataset, sequential runs, positive repeat count, fixed/reversed/seeded ordering, exact/boolean/graph scoring, checkpointed attempts, cancel/resume and JSON export. Demonstrate that every scheduled key runs exactly once unless a labelled retry occurs; seed/order `0` must work.
3. **Comparison workspace:** explicit parameter grids, per-repeat shuffles, raw responses, paired graph comparisons, CSV export and rescoring. Verify that equivalent encodings share their graph/query truth and that no context leaks between independent questions.
4. **Optional integrations:** import/export adapters for Inspect or Promptfoo, additional providers, shared-context experiments and advanced metrics. Keep an external-tool adapter behind the same manifest/provenance contract.

Before calling the mode ready, test a real CPU inference request through the application's authenticated path, inspect the effective `num_gpu: 0` request and loaded-model telemetry, run fresh repeated trials, interrupt/resume a run, and confirm exported totals match stored attempts. Record the installed runtime and model versions and any residual variability. Unit tests alone cannot establish CPU execution or determinism.

This investigation did not run model inference, install a benchmark framework, or implement the proposed mode.
