## Stack

* **Frontend:** Node.js 24, Next.js 16, React 19, TypeScript 7, shadcn/ui — `frontend/` — port `3000`
* **Backend:** Python 3.13, FastAPI, uv, Ruff, pytest — `backend/` — port `8000`
* **Local AI:** Ollama — `localhost:11434` — `gemma3:4b`
* **Cloud AI:** OpenAI, Anthropic, Grok, Meta, Gemini

## Commands

### Frontend

```bash
cd frontend
npm install
npm run dev
npm install <package-name>
```

### Backend

```bash
cd backend
uv sync
uv run fastapi dev
uv add <package-name>
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Rules

* Keep frontend code in `frontend/` and backend code in `backend/`.
* Use `uv` for Python dependencies and `npm` for frontend dependencies.
* Use Ruff for Python linting and formatting.
* Run relevant tests after every change.
* Keep changes minimal and follow existing patterns.
* Never commit `.env`, API keys, secrets, or credentials.
* Use environment variables for secrets.
* Do not introduce dependencies unless necessary.