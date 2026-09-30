FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY *.py ./

FROM python:3.13-slim-bookworm
WORKDIR /app
RUN useradd --create-home --uid 10001 agent
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER agent
# Model files some plugins need at runtime (cached in the image, not downloaded per session).
RUN python -m livekit.agents download-files
# LiveKit Agents serves a health check on 8081.
EXPOSE 8081
CMD ["python", "voice_agent.py", "start"]
