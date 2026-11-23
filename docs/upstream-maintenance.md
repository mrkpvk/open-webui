# Upstream maintenance for this fork

Recorded 9 November 2026. The scheduled task **Maintain Open WebUI fork** returns to the review chat on **Monday and Thursday at 10:00 Europe/London**. It is a local desktop task: keep the computer on, this checkout available and the app running. The schedule is configured in the app, not by this document.

## Identity and initial checkpoint

- Fork: [mrkpvk/open-webui](https://github.com/mrkpvk/open-webui), branch `main`.
- Confirmed GitHub parent/source: [open-webui/open-webui](https://github.com/open-webui/open-webui).
- Local reviewed fork head: `57c440271`, with pre-existing uncommitted installation/startup edits.
- Original upstream base: `ecd48e2f718220a6400ecf49eafd4867a38feb10` (0.10.2).
- Upstream inspected head: `b0e6098e940942281d9c83f3529ea117287a3a22`, [v0.13.3](https://github.com/open-webui/open-webui/releases/tag/v0.13.3).
- [Base-to-upstream comparison](https://github.com/open-webui/open-webui/compare/ecd48e2f718220a6400ecf49eafd4867a38feb10...b0e6098e940942281d9c83f3529ea117287a3a22) reported 3,397 upstream commits. This is not a claim that every commit merits integration.

## Why twice weekly

The latest 100 upstream commits inspected on 9 November span 7 November 15:26 to 8 November 23:48 UTC (about 32 hours). Their titles include 27 fixes, four features and one performance change; title classification is a useful activity proxy, not a full review of all 32 diffs. Ten published releases from 10 October to 8 November have a median inter-release gap of about 3.8 days. A Monday/Thursday check catches useful fixes without merging every refactor. Reassess the last month's substantive patches and releases monthly; use stable releases and applicable fixes as integration candidates.

## Behaviors every integration must preserve

1. CPU inference remains available through Ollama `num_gpu: 0`. Explicit zero seed and temperature values survive defaults, per-message overrides and provider conversion. Never switch an experiment to GPU for speed. CPU execution must be observed, not inferred from a control label.
2. Raw-context changes preserve other conversation branches, message metadata and attachments, and respect read-only conversations. An edited path becomes a separate branch rather than erasing the original.
3. Per-message generation controls affect the intended request, persist across regeneration/continuation, and preview the effective merge of chat and message settings.
4. N-gram diagnostics are post-generation warnings, not decoding enforcement. Frontend-only diagnostics must not be sent as unsupported Ollama options.
5. Existing secrets, settings, user data and unfinished work stay intact. Do not read or include secret files in patches or reports.
6. Preserve the separate `/benchmarks` mode, frozen manifests, owner-scoped checkpoints, CPU enforcement, pinned model/backend identity, exact scoring and cancellation/recovery behavior. Run the benchmark regressions with every relevant integration. Benchmark storage remains separate from chat storage.
7. Preserve public, integrity-verified npm tarball URLs and the fork's opt-in release guards. Ordinary maintenance pushes must not automatically publish packages/images or notify upstream projects.

CPU support is one feature among these requirements. Repeated identical output is a measured result under a recorded runtime/model/setup; no universal determinism claim follows from CPU use.

## Procedure on each scheduled run

Inspect current instructions, remotes, fork head and dirty state first. Compare upstream changes with this checkpoint and the maintenance log. Choose improvements for an actual defect or capability in this fork; inspect their dependencies and affected paths. Do not import the complete current upstream simply because a version number is newer.

Use an isolated `codex/upstream-*` branch/worktree based on the current fork. Leave a dirty user's checkout in place; do not stash it or commit their work implicitly. When needed, make a separate non-destructive snapshot for validation. Resolve overlaps by preserving the required behavior and regression tests, never by blanket replacement of custom files.

Run `npm run test:fork` and the backend regression command in `project-review.md`, plus relevant builds and affected upstream tests. Full checks already have baseline failures: compare those in an untouched fork snapshot under the same dependency environment and do not introduce new failures. Run live CPU checks for inference/runtime changes; unit tests prove request handling, not the device used by a model server. Build/dependency changes need a reproducible install check. A failed, unavailable or skipped relevant check is not a pass.

The user authorized useful merges. Integrate and push narrowly scoped, validated, low-risk changes to this user's fork when the destination is clean, the tested head remains current and the required checks pass. Use ordinary merges/fast-forwards, never force pushes. Do not change upstream settings or post upstream comments. Keep large upgrades, unresolved conflicts, data migrations and changes lacking adequate validation on a reviewable integration branch, with the remaining work explained. Do not pretend an untested update is safe.

Record candidate upstream SHAs, chosen/deferred changes, reasons, exact validation results, device/runtime evidence when relevant, integration head and next checkpoint. Report useful changes or action needed; keep unchanged checks brief.

## Initial integration log

9 November 2026: reviewed [upstream fix 842cd1f](https://github.com/open-webui/open-webui/commit/842cd1fa95894cde28d8d732357004b0d2b60119) and ported its `command -v ollama` build guard into this fork's Dockerfile. This makes the bundled-Ollama build fail when installation produces no executable. The change is in the working tree; it is not a full upstream merge or a published release. No Docker image build has yet validated it. The recent tool-call serialization fix `227287b3` targets a helper absent from this older fork, so it was not blindly transplanted.

The quality fixes and benchmark implementation validation are documented in [project-review.md](project-review.md). The implemented mode is covered in [benchmarking.md](benchmarking.md); the original research/design brief remains in [benchmarking-investigation.md](benchmarking-investigation.md). The tested pre-benchmark checkpoint was published at `527250fa9283e29056ab63aadb082eb066525312` on `backup/pre-benchmarks-2026-11-09`, and the original fork head is preserved on `backup/pre-review-2026-11-09`.

## 19 November 2026 maintenance

Reviewed the clean fork at `fc742255a19bd358447204b7eaa7d09bc4c660fe` against upstream `0666e59d26a4d056e0bacee41742486badd71cf8`, release [v0.13.4](https://github.com/open-webui/open-webui/releases/tag/v0.13.4), published 17 November. The comparison contains 330 commits since `b0e6098e940942281d9c83f3529ea117287a3a22`; paginated commit titles and release changes were triaged, with the selected fixes inspected at patch level. This is not an exhaustive audit of all 330 patches. The 12 and 16 November checks found no changes; their quiet check records are retained under the ignored `.codex-runtime-check/upstream-maintenance-*.json` paths.

Selected two dependency-free backports on isolated branch `codex/upstream-2026-11-19`:

- [a121ac4d0127082e0995af3df841ecc7ac0addab](https://github.com/open-webui/open-webui/commit/a121ac4d0127082e0995af3df841ecc7ac0addab): stop `createMessagesList` after the first repeated message ID. A malformed saved parent cycle previously froze the page. Valid selected branches retain their order, message references, attachments and parameter metadata; saved histories are not rewritten. Four regressions exercise the actual helper, including self/longer cycles, missing parents, frozen branches and zero CPU/seed/temperature overrides. Cyclic test fixtures have a read bound so a broken guard fails without hanging CI.
- [29b4af6b98a62cbc70c56c780b52854bb6cedea7](https://github.com/open-webui/open-webui/commit/29b4af6b98a62cbc70c56c780b52854bb6cedea7): move ten result/metadata logging calls across eight retrieval modules from INFO or stdout to lazy DEBUG logging. Search responses, filtering and error handling are unchanged. This reduces exposure of search results and file metadata in normal server logs; deliberately enabled DEBUG logs can still contain them.

Validation uses the existing dependency environment, Node 22.21.1 and Python 3.12.13:

- `npm run test:fork`: **23 passed**, including all original fork and benchmark frontend regressions. A bounded comparison with the original helper reproduced nontermination on a self-cycle and verified unchanged acyclic branch references/order after the patch.
- Backend pytest command from `project-review.md`, using a separate scratch temporary directory: **47 passed** on Windows, including actual normal-chat provider normalization and CPU-zero option checks.
- All eight edited Python modules compiled. AST comparison with the fork baseline confirmed that only the ten enumerated logging expressions changed. Synthetic captures verified result text is suppressed at INFO/stdout and retained at DEBUG, without changing input data. Full provider search functions and live search services were not exercised. Evidence is in the isolated worktree's ignored `.codex-runtime-check/logging-verification-result.json`.
- Targeted Prettier checks and `git diff --check` passed. Ruff was unavailable in the existing environment; no tool or dependency was installed for this level-only Python patch.
- Production Vite/adapter-static build: **passed in 2m 57s**, retaining inherited accessibility and bundle warnings. The first attempt hit a sandbox `EPERM` creating generated output; the repeat with the required output access passed on the same source. This compilation used the existing dependencies without rerunning optional Pyodide downloads or a fresh installation; package manifests and locks are unchanged.
- The inherited full-project type-check baseline of 9,521 errors / 282 warnings was not rerun or claimed fixed. No dependency, decoding option, provider route, benchmark manifest/storage, chat schema or CPU/GPU default changed. No fresh live-device observation is claimed for these changes; existing live CPU evidence remains in `project-review.md`.

The full 0.13.4 upgrade remains deferred: it changes terminal/direct-connection contracts and image configuration with migrations, requiring separate compatibility work. The rich-text highlighting fix `b4a88505e11764388655945e97ecfa556c434ab8` and image zoom fix `e48c15d87975a420dd8d191de773b9b1495911e3` remain possible follow-ups, with their own component behavior checks; neither is included here.

Next upstream comparison starts at `0666e59d26a4d056e0bacee41742486badd71cf8`. Keep the Monday/Thursday cadence; the monthly activity reassessment is due 9 December. Integration hashes, remote check results and any outstanding validation are recorded in `.codex-runtime-check/upstream-maintenance-2026-11-19.json` after publication.

Publication checks passed the fork regressions on Windows/Linux and Ruff formatting/logic checks on Python 3.11/3.12. Both full frontend jobs instead failed during dependency installation: the optional ONNX Runtime 1.21.0 CUDA archive returned 404. Their install inputs (`package.json`, npm lock, `.npmrc` and the workflow) were identical to the pre-maintenance checkpoint; no patched app code had run at the point of failure.

Applied the frontend-workflow portion of upstream [d67c707027ade0b86813c85d19449c787a9fd6a4](https://github.com/open-webui/open-webui/commit/d67c707027ade0b86813c85d19449c787a9fd6a4), setting `ONNXRUNTIME_NODE_INSTALL_CUDA=skip` only in that CI workflow. It skips an unused optional CUDA download; npm's bundled CPU binaries and the app's inference settings/defaults are unchanged. Docker and Python package build paths from that upstream patch are deferred because they need separate install/build validation. The subsequent GitHub workflow results are retained in the local check record above.

## 23 November 2026 maintenance

Upstream stable `main` remains at `0666e59d26a4d056e0bacee41742486badd71cf8` (v0.13.4). The development branch at `8f6f1d022c205505f3d9c6bd51173678c0a7e7f5` has diverged from stable. Reviewed the titles of 150 dev-side commits and inspected selected patches for applicability to fork head `7d7e1edd5762bbc008ba669a3da2b94b5a9279a6`.

Selected the spinner fix [01aae7268de156d440897a1d2a654252091f4d1f](https://github.com/open-webui/open-webui/commit/01aae7268de156d440897a1d2a654252091f4d1f) on `codex/upstream-2026-11-23`. It rotates the whole SVG at the same speed and size. In a headless Chrome 157 comparison using both versions of the fork component and a synthetic long chat with the existing shimmer animation, the old component caused 119 and 120 layout recalculations in two-second windows. The revised component caused zero in both windows. The fixture also confirmed matching dimensions, animation timing, paths and `aria-hidden` attributes. This measures browser layout for that fixture. It does not measure model inference or performance across browsers.

All 23 frontend and 47 backend fork regressions passed. The scoped patch affects browser presentation only. Production build and integration evidence are retained in the local `.codex-runtime-check/upstream-maintenance-2026-11-23.json` record.

Deferred the separate shimmer stylesheet changes and the math clipboard fix for browser compatibility checks. The context-usage optimisation targets an absent helper. The Chroma diagnostics and Qdrant connection changes need separate retrieval checks. The next stable checkpoint remains `0666e59d26a4d056e0bacee41742486badd71cf8`. The monthly schedule review remains due 9 December.
