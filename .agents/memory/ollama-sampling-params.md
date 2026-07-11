---
name: Ollama sampling parameter support
description: Which of the 5 investigated sampling params are supported by Ollama and how they are implemented
---

## Status (verified July 2025 against Ollama api/types.go Options struct)

| Parameter | Status | Implementation |
|---|---|---|
| typical_p | ✅ Native Ollama | Added to payload.py Ollama mappings + slider in AdvancedParams.svelte |
| no_repeat_ngram_size | ⚠️ Post-hoc client-side | Stripped from Ollama payload; client-side ngram.ts utility; warning badge in ResponseMessage.svelte |
| min_length | ❌ Not feasible | Stripped cleanly (open_webui_params); no UI rendered |
| ignore_eos | ❌ Not feasible | Stripped cleanly; no UI rendered |
| logit_bias | ❌ Ollama: no / OpenAI: yes | Existing UI kept; tooltip updated to "OpenAI-compatible only" |

## Bonus fix
tfs_z was in AdvancedParams UI and ollama-js interfaces but missing from payload.py Ollama mappings — silently dropped. Added tfs_z: float to mappings.

**Why:** Ollama's current api/types.go Options struct has: num_keep, seed, num_predict, top_k, top_p, min_p, typical_p, repeat_last_n, temperature, repeat_penalty, presence_penalty, frequency_penalty, stop. mirostat/tfs_z not in struct but passed through for llama.cpp runner compatibility.

## Key files changed
- backend/open_webui/utils/payload.py — typical_p + tfs_z in Ollama mappings; no_repeat_ngram_size/min_length/ignore_eos in open_webui_params
- src/lib/components/chat/Settings/Advanced/AdvancedParams.svelte — typical_p slider, no_repeat_ngram_size control, logit_bias tooltip fix
- src/lib/utils/ngram.ts (new) — detectNgramRepetition()
- src/lib/components/chat/Messages/ResponseMessage.svelte — ngramRepetitionWarning reactive + amber warning badge
- docs/ollama-sampling-params-status.md (new) — full written status table
