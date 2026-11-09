# Ollama Sampling Parameter Support Status

Review update, 9 November 2026: the historical implementation notes below are not a compatibility guarantee. The installed Ollama 0.32.1 [Options/Runner source](https://github.com/ollama/ollama/blob/v0.32.1/api/types.go) includes `typical_p`, `num_gpu`, `num_thread`, `num_batch` and `num_ctx`; it does not list `tfs_z` or the `mirostat` family. These legacy controls remain in this fork for older backends, but their presence in the UI or outgoing options does not prove the server honors them. The [current main source](https://github.com/ollama/ollama/blob/main/api/types.go) marks `typical_p` deprecated as a model parameter while still accepting it per request with a warning. Check the exact installed server version for experiments.

Standard chat and direct model-option paths now share normalization. Frontend-only `no_repeat_ngram_size` is stripped after custom-parameter merging; Ollama-only stripping of `min_length`, `ignore_eos` and `logit_bias` no longer removes those options from other compatible providers. Explicit `num_gpu: 0`, `seed: 0`, `temperature: 0`, and `think: false` survive conversion. See [review and validation](project-review.md) for test coverage and CPU runtime evidence.

The remaining notes record the original July 2025 investigation and should be read with these corrections.

## Original supported-options inventory

| Parameter                    | Ollama field        | Notes     |
| ---------------------------- | ------------------- | --------- |
| `temperature`                | `temperature`       | ✅ Native |
| `top_p`                      | `top_p`             | ✅ Native |
| `top_k`                      | `top_k`             | ✅ Native |
| `min_p`                      | `min_p`             | ✅ Native |
| `repeat_penalty`             | `repeat_penalty`    | ✅ Native |
| `frequency_penalty`          | `frequency_penalty` | ✅ Native |
| `presence_penalty`           | `presence_penalty`  | ✅ Native |
| `seed`                       | `seed`              | ✅ Native |
| `num_predict` (`max_tokens`) | `num_predict`       | ✅ Native |
| `stop`                       | `stop`              | ✅ Native |
| `repeat_last_n`              | `repeat_last_n`     | ✅ Native |

## Five parameters investigated

### 1. typical_p

**Status: ✅ Natively supported by Ollama**

Confirmed in `api/types.go`:

```go
TypicalP float32 `json:"typical_p,omitempty"`
```

Default value is `1.0` (disabled). Values below 1.0 apply locally-typical sampling.

**Action taken:** Added `typical_p: float` to the Ollama mappings in `payload.py` and added a UI slider (0.0–1.0) in `AdvancedParams.svelte` labeled `typical_p (Ollama)`.

---

### 2. no_repeat_ngram_size

**Status: ⚠️ Not supported by Ollama — post-generation client-side approximation**

Ollama's `Options` struct has no `no_repeat_ngram_size` field. This fork implements a word-level text diagnostic after generation, not the token-level decoding constraint in Hugging Face Transformers.

`repeat_last_n` is a different mechanism: it penalises recently-seen _tokens_ by adjusting their logit score; it does not hard-block exact n-gram sequences.

**Action taken:**

- Parameter is stripped from the Ollama options payload (added to `open_webui_params` in `payload.py`).
- UI control added in `AdvancedParams.svelte` with an info tooltip explaining this is a post-generation check.
- Client-side `detectNgramRepetition()` in `src/lib/utils/ngram.ts` runs on the completed response. A warning badge appears on the message when a repeated n-gram is detected.

---

### 3. min_length (minimum tokens)

**Status: ❌ Not supported by Ollama — not feasible via streaming API**

Ollama's `Options` struct has no `min_length` or equivalent field. The only approach would be to intercept the streaming response and re-request continuation when the model emits EOS before the minimum token count is reached, but this would break the SSE streaming architecture without major refactoring.

**Action taken:** Not implemented. No UI control rendered (per principle: do not show a control for something the backend silently ignores). Documented here.

---

### 4. ignore_eos / end-of-generation token control

**Status: ❌ Not supported by Ollama — not feasible**

`stop` sequences are the only termination lever exposed by Ollama. There is no `--ignore-eos` equivalent in Ollama's API. llama.cpp exposes `--ignore-eos` as a CLI flag, but this is a server-level flag, not a per-request option.

Since `stop` sequences and `min_length` are the only mechanisms, and `min_length` is itself not feasible (see above), EOS control is not implementable without bypassing Ollama entirely.

**Action taken:** Not implemented. No UI control rendered.

---

### 5. logit_bias

**Status: ❌ Not supported by Ollama — OpenAI-compatible APIs only**

Ollama's `Options` struct has no `logit_bias` field. The OpenAI `/v1/chat/completions` path does support it (passed directly in the request body per the OpenAI spec).

Using a raw llama.cpp server instance would allow logit bias via `/completion` endpoint's `logit_bias` array field, but this would require a separate "advanced backend" connection mode — significant scope expansion.

**Action taken:** The existing `logit_bias` UI control is retained (it works for OpenAI-compatible backends). The tooltip is updated to explicitly note OpenAI-compatible APIs only, so users with an Ollama backend know it has no effect.

---

## tfs_z (tail-free sampling)

**Historical finding:** `tfs_z` was present in the UI `defaultParams` and in older `ollama-js` interfaces but missing from Open WebUI's Ollama `payload.py` mappings. Passing it through fixes that omission for compatible older servers; it does not establish support in Ollama 0.32.1.

**Action taken:** Added `'tfs_z': float` to the Ollama mappings in `payload.py`.
