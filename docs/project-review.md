# Fork review and validation

Reviewed 9 November 2026, starting from local fork head `57c440271`. The review concentrated on the fork's custom behavior relative to upstream base `ecd48e2f7`, plus startup, provider request handling, dependencies and integration checks. It is not a line-by-line audit of every inherited upstream feature.

The useful custom additions are the raw-context editor, per-message parameter controls, expanded sampling options and repetition diagnostics. Their main quality issues were inconsistent handling between layers and missing regression coverage. The inherited app also has substantial type-check debt. These changes repair concrete behavior and add checks that future upstream integrations must retain.

Pre-existing local edits to `.npmrc`, `backend/.gitignore`, `backend/start_windows.bat` and `package.json`, and the local pnpm files, were preserved. The existing secret file was not read, rotated or committed. At the end of this initial review the changes were uncommitted. On the user's subsequent instruction, they were committed and published as checkpoint `527250fa9283e29056ab63aadb082eb066525312` on the fork's [pre-benchmark backup branch](https://github.com/mrkpvk/open-webui/tree/backup/pre-benchmarks-2026-11-09). No live user-data migration or wholesale upstream upgrade was performed.

## Repairs

| Area | Defect and repair |
| --- | --- |
| Raw-context edits | Saving replaced the complete history map, losing other branches, attachments, model fields and overrides. Edited paths now become a new branch while retaining original messages. Stale structured output is removed when content/role changes so it cannot hide the edited text. Root navigation exposes both original and edited paths. |
| Editor lifecycle | Saving now waits for persistence before closing, prevents duplicate Apply requests, and guards chat navigation during saving. Read-only conversations and active generation cannot open the editor. |
| Message parameters | Requests, preview and repetition diagnostics now share explicit global → chat → user-message → response-message precedence. Null means inherit. Zero seed/temperature/GPU count, false values and empty stop lists survive. Response overrides persist and affect regeneration/continuation. Opening the panel no longer triggers redundant saves. |
| Stop sequences | Per-message strings now use the same conversion as chat settings. Literal percent signs and malformed escape sequences no longer abort request construction. Already-literal lists preserve whitespace, commas, newlines and percent escapes exactly. |
| Ollama requests | Normal chat previously bypassed the fork's provider normalizer. It now shares conversion with direct model settings. Frontend diagnostics are removed after custom-parameter merging; provider-specific options remain available to compatible providers. `max_tokens` becomes `options.num_predict`, and root `think: false` survives. Reusing settings no longer consumes them through mutation. |
| Repetition diagnostics | Completed responses use the effective configured size and visible text. Detection now handles overlapping repeats and Unicode words. This is a warning after generation, not enforced token decoding. |
| Startup and secrets | Fixed the misspelled secret ignore rule. Windows startup supports the project Python or an activated environment, preserves exclamation marks in keys, and quotes paths/proxy arguments correctly. New Windows/CLI keys use cryptographic randomness and exclusive creation; existing keys stay intact. |
| Dependencies and tests | Repaired the stale npm lock for the declared CodeMirror dependencies. Replaced incompatible Vitest 4 with Vitest 3.2.7 for existing Vite 5.4.21, updating both locks without broad upgrades. Added an isolated fork test configuration and CI on Linux plus Windows backend checks. [Vitest 3 requirements](https://v3.vitest.dev/guide/), [versioned dependency contract](https://github.com/vitest-dev/vitest/blob/v3.2.7/packages/vitest/package.json). |
| Upstream build guard | Ported the small upstream Ollama-install check to the Dockerfile; see the source and limits in [upstream-maintenance.md](upstream-maintenance.md). |

## CPU inference: measured evidence

CPU remains supported as requested. Both request-layer regressions and live inference were checked:

- Installed Ollama **0.32.1**, existing model **gemma3:1b**, digest `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc`.
- Settings: `num_gpu=0`, `num_thread=1`, `num_batch=512`, `num_ctx=512`, `seed=0`, `temperature=0`, generated-token limit 8.
- Three direct Ollama requests returned exactly `READY\n`; each loaded-model observation reported `size_vram=0`.
- Three further requests through the app's **authenticated `/api/chat/completions` route** returned the same exact output, finish reason `stop`, and 17 input/3 output tokens. Each observation again reported `size_vram=0`. These included the client-only repetition setting, verifying it did not break the provider request.
- The app check used an isolated fresh data directory, offline mode and a synthetic temporary account. User accounts, settings and data were not used. Temporary server processes owned by the check were stopped and the model unloaded.

Sanitized evidence is retained locally in `.codex-runtime-check/cpu-smoke-result.json` and `.codex-runtime-check/app-cpu-smoke-result.json`. The whole scratch directory is ignored because it also contains temporary app state. No account token/password is included in those reports.

This establishes working CPU inference through the app and repeatability for these six short trials. It does not establish universal determinism, every model/parameter combination, browser UI behavior or long-run benchmark reproducibility. An initial deliberately tiny `num_batch=1` probe hit an Ollama runner assertion; the successful checks use the normal batch setting above. Do not use batch size one as a blanket determinism recipe.

The likely referenced Thinking Machines article also discusses batch-related nondeterminism on CPU endpoints. Preserve the requested CPU path and measure output identity under a frozen environment. [Original article](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/).

## Repeatable checks

Frontend fork regressions:

```powershell
npm run test:fork
```

Backend regressions with the existing project environment:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=.codex-runtime-check/pytest
```

The nine backend tests run the actual conversion helpers and normal-chat normalizer without booting user databases, and check CLI key creation/preservation. Windows tests exercise the real batch launcher with a harmless fake uvicorn module and synthetic keys. The thirteen frontend tests cover branch/metadata preservation, malformed histories, effective parameter resolution, stop sequences and repetition detection. The new `.github/workflows/fork-regressions.yaml` runs them on pull requests and pushes; remote CI has not yet run for these uncommitted changes.

Observed checks so far:

| Check | Result |
| --- | --- |
| `npm run test:fork` | 13 passed on Vitest 3.2.7. |
| Backend pytest suite | 9 passed on Windows. |
| Edited Svelte component compilation | All nine modified components compiled. |
| New utility strict TypeScript check | Passed for all three utilities. |
| npm clean-install dry-run, scripts disabled | Passed; validates lock/install planning, not a complete fresh dependency build. |
| Existing installed direct dependencies | All 137 declarations matched pnpm resolutions after the targeted Vitest repair. |
| Initial production Vite build | Passed with existing accessibility/large-bundle warnings. |
| Full type check before repairs | Failed: 9,574 errors and 282 warnings in 378 files. |
| Full type check after repairs | Still fails: 9,521 errors and 282 warnings in 378 files, down by 53 errors. No added diagnostic messages in the reviewed Message/ResponseMessage/RawContextEditor components; new helpers have no diagnostics. |
| Python formatting and focused logic lint | Ruff 0.15.5 format plus the existing CI's F-rule subset passed on changed Python files. |
| Final production build | Passed on the final source with Vite/adapter-static in 2m 44s; generated site written to `build`. Existing accessibility and bundle-size warnings remain. A prior sandbox output-directory permission failure was resolved by running the final build with the required filesystem access. |

The production build check invokes Vite directly using already-prepared Pyodide assets. It does not test downloading all optional browser Python packages. npm and pnpm locks now match the manifest, but their pre-existing resolutions differ for other dependencies; use a recorded installer/lock consistently when comparing baseline results. No blanket dependency upgrade was included.

## Maintenance and benchmarking

The active Monday/Thursday maintenance task and the protected behaviors are described in [upstream-maintenance.md](upstream-maintenance.md). A 3,397-commit upstream gap warrants selected fixes and staged upgrades with behavioral checks, rather than replacing custom files.

[benchmarking-investigation.md](benchmarking-investigation.md) records the initial research. The subsequent requested implementation is described in [benchmarking.md](benchmarking.md).

## Benchmark implementation validation

The user subsequently requested implementation and publication to their fork with a saved rollback version. Both the original fork and the tested review checkpoint were saved as remote backup branches before the feature was added.

- **66 regression tests passed:** 47 Python tests and 19 frontend tests. New coverage checks scheduling, strict scoring, zero seeds, CPU option validation, dataset imports, owner isolation, preset-policy preservation, lease contention, cancellation/retry history, expired-worker recovery, reasoning variability and accuracy denominators.
- **Production Vite build passed**, including the new route and sidebar link. The full type check remains at the existing baseline of **9,521 errors / 282 warnings**; the new benchmark page, client and dataset utilities produced no diagnostics.
- Real authenticated CPU experiments verified an eight-trial configuration comparison and JSON/CSV exports, a 20-trial cancellation/resume experiment, and a 40-trial restart experiment. The restart interrupted an active worker; 37 completed outputs were preserved and the remaining trials resumed after lease recovery. No duplicated completed attempts were introduced.
- Cross-account read/export returned 404, unauthenticated read returned 401, a GPU override returned 422, and competing start returned 409.
- Browser testing saved and started the built-in directed-graph dataset with `gemma3:1b`, one configuration and two repeats. All six requests finished without transport errors; the oracle scored **33.3% accuracy**, with **100% answer agreement and raw-output identity**. These are validation observations for a tiny fixture, not a model-quality estimate. The screenshot in `docs/assets/benchmarks.png` shows the results.
- The benchmark API evidence and restart evidence are saved locally under the ignored `.codex-runtime-check` directory. All testing used isolated app data and synthetic accounts. The temporary servers are stopped after validation.

The current limits and deferred features are documented in the benchmarking guide. No new runtime dependencies or chat-database migrations were added by this feature.
