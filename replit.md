# Open WebUI

A feature-rich, self-hosted AI chat platform that supports Ollama, OpenAI-compatible APIs, and many other LLM backends. Full-stack app: Python/FastAPI backend + SvelteKit frontend.

## Stack

- **Backend**: Python (FastAPI + uvicorn), located in `backend/open_webui/`
- **Frontend**: SvelteKit + Tailwind CSS, located in `src/`
- **Package manager**: `uv` (Python), `npm` (Node/frontend)

## Running the app

The workflow `Start application` runs:

```bash
source .venv/bin/activate && bash backend/start.sh
```

This starts the uvicorn server on port 8080. The frontend must be built first (`npm run build`) — the FastAPI backend serves the built SvelteKit output as static files.

For development with a live frontend:

```bash
npm run dev   # starts Vite dev server on port 5173
```

## Key environment variables (see `.env.example`)

- `OLLAMA_BASE_URL` — URL of a running Ollama instance (default: `http://localhost:11434`)
- `OPENAI_API_KEY` / `OPENAI_API_BASE_URL` — for OpenAI or compatible API backends
- `WEBUI_SECRET_KEY` — JWT secret (auto-generated to `backend/.webui_secret_key` if unset)

## Active development focus

Per-message sampling/generation parameter override system for Ollama's `/api/chat` and `/api/generate`. Parameters already confirmed working: `temperature`, `top_k`, `top_p`, `min_p`, `repeat_penalty`, `frequency_penalty`, `presence_penalty`, `seed`, `num_predict`, `stop`.

Parameters under investigation: `typical_p`, no-repeat n-gram size, minimum tokens, EOS token control, logit bias.

## User preferences
