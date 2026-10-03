#!/usr/bin/env bash
# Every quality gate for a Sentiment Studio project. Exits non-zero on the first failure (CI-safe).
#
#   bash verify.sh <project-dir>          # api + web
#   bash verify.sh <project-dir> --api    # backend only
#   bash verify.sh <project-dir> --web    # frontend only
set -euo pipefail

ROOT="${1:?usage: verify.sh <project-dir> [--api|--web]}"
ONLY="${2:-}"
ROOT="$(cd "$ROOT" && pwd)"
step() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
want() { [[ -z "$ONLY" || "$ONLY" == "--$1" ]]; }

if want api; then
  step "api: install (uv sync)"
  (cd "$ROOT/api" && uv sync --quiet)
  step "api: ruff lint"
  (cd "$ROOT/api" && uv run ruff check .)
  step "api: ruff format check"
  (cd "$ROOT/api" && uv run ruff format --check .)
  step "api: pytest (tiny local checkpoints, no downloads)"
  (cd "$ROOT/api" && uv run pytest)
fi

if want web; then
  step "web: install"
  if [[ -d "$ROOT/web/node_modules" ]]; then
    echo "node_modules present, skipping install"
  else
    (cd "$ROOT/web" && npm ci --no-audit --no-fund)
  fi
  step "web: typecheck (TypeScript 7)"
  (cd "$ROOT/web" && npm run typecheck)
  step "web: production build"
  (cd "$ROOT/web" && NEXT_TELEMETRY_DISABLED=1 npm run build)
fi

printf '\n\033[32m✓ All checks passed\033[0m\n'
