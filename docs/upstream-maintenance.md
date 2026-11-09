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
