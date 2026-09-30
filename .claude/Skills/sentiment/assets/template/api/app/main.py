"""FastAPI entrypoint.

uv run fastapi dev        # development, http://localhost:8000 (docs at /docs)
uv run fastapi run        # production
"""

from app.factory import create_app

app = create_app()
