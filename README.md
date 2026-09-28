# BIS Compliance & Intelligence Assistant (BIS Sahayta)

AI-powered compliance and standards assistant for the Bureau of Indian Standards (BIS).

## Setup & Running

### Backend Server (FastAPI)

1. Navigate to `backend`:
   ```powershell
   cd backend
   ```
2. Copy configuration and populate variables:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Set your `GEMINI_API_KEY` in `backend/.env`.
4. Run server:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Web UI (React + Vite)

1. Navigate to `frontend`:
   ```powershell
   cd frontend
   ```
2. Install pinned dependencies:
   ```powershell
   npm ci
   ```
3. Run dev server:
   ```powershell
   npm run dev
   ```

## Environment Variables

- `API_KEY`: Authentication key for API routes (default: `demo-key-123`)
- `LLM_PROVIDER`: Selected LLM provider (`gemini` | `ollama` | `mock`)
- `GEMINI_API_KEY`: Google AI Studio API key
- `GEMINI_MODEL`: Model name (default: `gemini-2.5-flash`)
- `VECTORSTORE_PATH`: Path to FAISS vector index directory (`backend/storage/vectorstore`)

## Smoke Verification

Run the automated PowerShell verification script:
```powershell
.\scripts\smoke.ps1
```
