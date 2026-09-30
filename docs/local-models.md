# Local Models — Setup Guide

> **TL;DR:** BIS Sahayta supports automatic fallback from Gemini to self-hosted open-weight models (Gemma 4, Qwen) when Gemini hits rate limits or quota errors. This document explains how to set them up.

---

## Architecture

```
User Request
     │
     ▼
 LLMRouter (auto mode)
     │
     ├─► Gemini 2.5 Flash ──── OK ──► Answer  ← fastest, default
     │       │
     │     429 / 5xx / timeout
     │       │
     ├─► Gemma 4 (local) ──── OK ──► Answer  ← fallback 1
     │       │
     │     error
     │       │
     └─► Qwen 2.5 (local) ─── OK ──► Answer  ← fallback 2
             │
           error
             │
           503 LLM_ALL_FAILED
```

The router uses a **circuit breaker**: after Gemini returns a 429/quota error it is skipped for `LLM_COOLDOWN_SECONDS` (default: 60 s) so subsequent requests go straight to local models without waiting for a failing call.

---

## Prerequisites

Install [Ollama](https://ollama.com/download) (simplest) **or** run [llama.cpp llama-server](https://github.com/ggerganov/llama.cpp) — both expose an OpenAI-compatible `/v1/chat/completions` endpoint.

---

## Option A — Ollama (recommended for most setups)

### 1. Install Ollama

```bash
# Windows: download and run the installer from https://ollama.com/download
# Linux/macOS:
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull models

```bash
# Gemma 4 (4 B parameters — needs ~4 GB VRAM or ~8 GB RAM)
ollama pull gemma3:4b

# Qwen 2.5 (7 B parameters — needs ~6 GB VRAM or ~12 GB RAM)
ollama pull qwen2.5:7b
```

### 3. Start Ollama server

```bash
ollama serve
# Server listens on http://localhost:11434 by default
```

Ollama serves an OpenAI-compatible endpoint at `http://localhost:11434/v1`.

### 4. Verify

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma3:4b",
    "messages": [{"role": "user", "content": "What is BIS?"}],
    "max_tokens": 50
  }'
```

---

## Option B — llama.cpp llama-server

```bash
# Build llama.cpp (GPU or CPU build — see llama.cpp docs)
# Then run the server:
./llama-server \
  -m models/gemma-3-4b-it-q4_k_m.gguf \
  --host 0.0.0.0 --port 8080 \
  --ctx-size 4096
```

Set `GEMMA4_BASE_URL=http://localhost:8080/v1` in your `.env`.

---

## Environment Variables

Add these to `backend/.env` (copy from `backend/.env.example`):

```dotenv
# Which model to use by default: auto | gemini | gemma4 | qwen
LLM_DEFAULT_MODEL=gemini

# Comma-separated fallback order when the primary model fails
LLM_FALLBACK_ORDER=gemma4,qwen

# HTTP timeout for local model calls (seconds)
LLM_REQUEST_TIMEOUT_SECONDS=30

# Max concurrent requests to local models (protects GPU memory)
LLM_LOCAL_MAX_CONCURRENCY=2

# Skip Gemini for this many seconds after a 429/quota error
LLM_COOLDOWN_SECONDS=60

# Gemma 4 endpoint (Ollama OpenAI-compat)
GEMMA4_BASE_URL=http://localhost:11434/v1
GEMMA4_MODEL_NAME=gemma3:4b
GEMMA4_API_KEY=        # leave blank for unauthenticated local server

# Qwen endpoint (Ollama OpenAI-compat)
QWEN_BASE_URL=http://localhost:11434/v1
QWEN_MODEL_NAME=qwen2.5:7b
QWEN_API_KEY=          # leave blank for unauthenticated local server
```

> **If `GEMMA4_BASE_URL` or `GEMMA4_MODEL_NAME` are left blank** the model is silently marked as unavailable and skipped — the app never crashes at startup.

---

## API Usage

### Select model per-request

Add `"model"` to the chat payload:

```bash
# Use Gemini explicitly
curl -X POST http://localhost:8000/api/chat \
  -H "X-API-Key: demo-key-123" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is IS 1647?", "model": "gemini"}'

# Use Gemma 4 explicitly
curl -X POST http://localhost:8000/api/chat \
  -H "X-API-Key: demo-key-123" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is IS 1647?", "model": "gemma4"}'

# Auto (default) — Gemini first, then fallback chain
curl -X POST http://localhost:8000/api/chat \
  -H "X-API-Key: demo-key-123" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is IS 1647?", "model": "auto"}'
```

The response includes routing metadata:

```json
{
  "reply": "IS 1647 ...",
  "model_used": "gemma4",
  "fallback_used": true,
  "fallback_reason": "Gemini rate limit reached. Please retry shortly."
}
```

### Check model availability

```bash
curl http://localhost:8000/api/models \
  -H "X-API-Key: demo-key-123"
```

```json
{
  "models": [
    {"key": "gemini", "label": "Gemini (Google)", "available": true,  "reason": null},
    {"key": "gemma4", "label": "Gemma 4",         "available": true,  "reason": null},
    {"key": "qwen",   "label": "Qwen",             "available": false, "reason": "Not configured ..."}
  ],
  "default": "gemini"
}
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `LLM_NOT_CONFIGURED` | Set `GEMMA4_BASE_URL` and `GEMMA4_MODEL_NAME` in `.env` |
| `LLM_PROVIDER_OFFLINE` | Make sure `ollama serve` is running |
| `LLM_TIMEOUT` | Increase `LLM_REQUEST_TIMEOUT_SECONDS` or use a smaller model |
| `LLM_ALL_FAILED` | All configured models are down/unconfigured |
| Gemini skipped immediately | Circuit breaker is active — wait `LLM_COOLDOWN_SECONDS` or restart |
| Slow first response | Model loading into VRAM — subsequent calls are faster |

---

## Resource Requirements

| Model | VRAM | RAM (CPU fallback) | Notes |
|---|---|---|---|
| `gemma3:4b` | ~4 GB | ~8 GB | Good quality, fast |
| `gemma3:12b` | ~10 GB | ~20 GB | Higher quality |
| `qwen2.5:7b` | ~6 GB | ~12 GB | Strong multilingual |
| `qwen2.5:14b` | ~12 GB | ~24 GB | Best quality |

---

## Security Notes

- Local model endpoints (`GEMMA4_BASE_URL`, `QWEN_BASE_URL`) are **backend-only** — never exposed to the frontend.
- The frontend only sends the model _key_ (`auto`, `gemini`, `gemma4`, `qwen`).
- Never commit real API keys to version control. Always use `.env` (which is `.gitignore`d).
