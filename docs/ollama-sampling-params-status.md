# Ollama Sampling Parameter Support Status

Verified against Ollama `api/types.go` (Options struct) as of July 2025.
See: https://github.com/ollama/ollama/blob/main/api/types.go

## Already confirmed working (in Ollama `Options` struct or accepted by llama.cpp runner)

| Parameter | Ollama field | Notes |
|---|---|---|
| `temperature` | `temperature` | ✅ Native |
| `top_p` | `top_p` | ✅ Native |
| `top_k` | `top_k` | ✅ Native |
| `min_p` | `min_p` | ✅ Native |
| `repeat_penalty` | `repeat_penalty` | ✅ Native |
| `frequency_penalty` | `frequency_penalty` | ✅ Native |
| `presence_penalty` | `presence_penalty` | ✅ Native |
| `seed` | `seed` | ✅ Native |
| `num_predict` (`max_tokens`) | `num_predict` | ✅ Native |
| `stop` | `stop` | ✅ Native |
| `repeat_last_n` | `repeat_last_n` | ✅ Native |

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

Ollama's `Options` struct has no `no_repeat_ngram_size` field. The underlying llama.cpp also does not expose this as a sampling parameter (it is a Hugging Face Transformers beam-search feature).

`repeat_last_n` is a different mechanism: it penalises recently-seen *tokens* by adjusting their logit score; it does not hard-block exact n-gram sequences.

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

**Bonus finding:** `tfs_z` is present in the UI `defaultParams` and in the `ollama-js` interfaces but was missing from Open WebUI's Ollama `payload.py` mappings, meaning it was silently dropped before reaching Ollama.

**Action taken:** Added `'tfs_z': float` to the Ollama mappings in `payload.py`.
