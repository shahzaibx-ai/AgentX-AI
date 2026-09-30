---
name: uv-project-scaffold
description: Scaffold a new Python API/backend project with uv using a flat app/ layout (app/main.py, app/__init__.py), no build system, .env and .env.example files, and a production-ready .gitignore. Use when the user asks to start, create, bootstrap, initialize or scaffold a Python, uv, API or backend project.
compatibility: Requires uv 0.12+ and git. Works on macOS, Linux and Windows.
metadata:
  version: "2.0"
---

# uv Project Scaffold

Creates a Python project called `api` with [uv](https://docs.astral.sh/uv/), using a flat `app/` package instead of uv's default `src/` layout, environment files, and a production-ready `.gitignore`.

## Golden rules

- **uv manages everything.** Install packages only with `uv add`, remove with `uv remove`, run with `uv run`.
- **Never create a virtual environment manually.** No `python -m venv`, no `virtualenv`, no `pip install`, no `source .venv/bin/activate`. uv creates and manages `.venv` automatically on `uv sync` / `uv run` / `uv add`.
- **Never commit `.env`.** Only `.env.example` goes into git.

## Why `--no-package`

Since uv 0.12, plain `uv init` creates a `src/<project_name>/__init__.py` layout and adds `[project.scripts]` and a `[build-system]` using `uv_build`. An API is an application, not an installable library, so this skill uses `uv init --no-package`, which skips the build system, and then sets `[tool.uv] package = false` explicitly so uv never tries to build or install the project.

## Prerequisites

```bash
uv --version
```

If uv is missing, install it:

- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

If uv is older than 0.12, update it with `uv self update`.

## Steps

`<skill-dir>` below means the folder containing this SKILL.md. On Windows, use the PowerShell equivalents (`Copy-Item`, `Remove-Item`).

1. **Create the project without a build system**

   ```bash
   uv init --no-package api
   cd api
   ```

   This creates `pyproject.toml`, `.python-version`, `README.md`, `.gitignore`, a placeholder `main.py`, and a git repository.

2. **Replace the placeholder with the `app/` package**

   ```bash
   rm main.py
   cp -r <skill-dir>/assets/app ./app
   ```

   `app/__init__.py` marks it as a package, and `app/main.py` is the entry point.

3. **Mark the project as non-packaged**

   Append this to the end of `pyproject.toml`:

   ```toml
   [tool.uv]
   package = false
   ```

   The final `pyproject.toml` must NOT contain `[project.scripts]` or `[build-system]`. If either is present (for example, the project was created with plain `uv init`), delete both sections and delete the `src/` folder.

4. **Add the production `.gitignore`**

   ```bash
   cp <skill-dir>/assets/gitignore .gitignore
   ```

   This replaces uv's minimal `.gitignore`. It ignores `.env` and every `.env.*` file except `.env.example`.

5. **Create the environment files**

   ```bash
   cp <skill-dir>/assets/env.example .env.example
   cp .env.example .env
   ```

   `.env.example` is the committed template with placeholder values. `.env` holds real local values and stays out of git.

6. **Sync the environment**

   ```bash
   uv sync
   ```

   uv creates `.venv` and writes `uv.lock`.

7. **Run it**

   ```bash
   uv run --env-file .env python -m app.main
   ```

   Expected output:

   ```
   Hello, World! 👋 api is running in development mode.
   ```

   Always run from the project root with `python -m app.main` so imports like `from app.config import settings` work.

8. **Verify**

   ```bash
   git check-ignore .env        # must print: .env
   git check-ignore .env.example  # must print nothing
   ```

   Also confirm `pyproject.toml` contains `[tool.uv] package = false` and no `[build-system]`.

## Result

```
api/
├── .env               # real values, ignored by git
├── .env.example       # template, committed
├── .gitignore
├── .python-version
├── .venv/             # created by uv, never by hand
├── README.md
├── app/
│   ├── __init__.py
│   └── main.py
├── pyproject.toml
└── uv.lock
```

Final `pyproject.toml`:

```toml
[project]
name = "api"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[tool.uv]
package = false
```

(`requires-python` matches the Python version uv found or pinned.)

## Handy next commands

| Task | Command |
|---|---|
| Add a package | `uv add fastapi` |
| Add a dev package | `uv add --dev pytest ruff` |
| Remove a package | `uv remove fastapi` |
| Upgrade one package | `uv lock --upgrade-package fastapi` |
| Pin Python version | `uv python pin 3.13` |
| Run with env vars | `uv run --env-file .env python -m app.main` |
| Run tests | `uv run pytest` |
| Lint and format | `uv run ruff check .` / `uv run ruff format .` |
| Install exactly from lockfile (CI/prod) | `uv sync --locked` |
| Skip dev deps in production | `uv sync --locked --no-dev` |

## Notes

- If an `api` folder already exists, ask the user before overwriting, or pick another name.
- If the user gives a different project name, use it instead of `api` everywhere, including `APP_NAME` in `.env.example`. Keep the package folder named `app/`.
- To load `.env` inside the code instead of via `--env-file`, install it with `uv add python-dotenv` (never pip).
- Keep `.env.example` in sync: whenever a new variable is added to `.env`, add it to `.env.example` with a placeholder value.
- Commit `uv.lock` so every machine and deployment gets identical dependency versions.
