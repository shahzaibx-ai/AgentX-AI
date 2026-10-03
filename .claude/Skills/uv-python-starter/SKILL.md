---
name: uv-python-starter
description: Scaffold a new Python backend project with uv (init, run, sync) and a Hello World entry point. Use when the user asks to start, bootstrap or scaffold a Python/uv project or backend.
---

# uv Python Starter

Creates a minimal Python project called `backend` using [uv](https://docs.astral.sh/uv/), drops in a Hello World `main.py`, runs it, and syncs the environment.

## Prerequisites

Check that uv is installed:

```bash
uv --version
```

If it is missing, install it:

- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Or: `pip install uv`

## Steps

1. **Create the project**

   ```bash
   uv init backend
   cd backend
   ```

   This creates `pyproject.toml`, `.python-version`, `README.md`, `.gitignore` and a starter `main.py`.

2. **Add the Hello World entry point**

   Copy `scripts/main.py` from this skill into the project, replacing uv's default:

   ```bash
   cp <skill-dir>/scripts/main.py ./main.py
   ```

3. **Run it**

   ```bash
   uv run main.py
   ```

   Expected output:

   ```
   Hello, World! 👋 Your uv backend is running.
   ```

   `uv run` creates the `.venv` automatically on first use.

4. **Sync the environment**

   ```bash
   uv sync
   ```

   Installs everything in `pyproject.toml` and writes `uv.lock`.

## Result

```
backend/
├── .gitignore
├── .python-version
├── .venv/
├── README.md
├── main.py
├── pyproject.toml
└── uv.lock
```

## Handy next commands

| Task | Command |
|---|---|
| Add a package | `uv add fastapi` |
| Add a dev package | `uv add --dev pytest` |
| Remove a package | `uv remove fastapi` |
| Pin Python version | `uv python pin 3.12` |
| Run any tool | `uv run pytest` |

## Notes

- If a `backend` folder already exists, ask the user before overwriting or pick another name.
- If the user names the project differently, use that name instead of `backend` everywhere.