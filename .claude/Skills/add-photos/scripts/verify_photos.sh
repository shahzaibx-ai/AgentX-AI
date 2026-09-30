#!/usr/bin/env bash
# Quality gates for a project with "Add photos" installed.
#
#   bash verify_photos.sh <project-dir>            # wiring + api + web
#   bash verify_photos.sh <project-dir> --api      # or --web / --wiring
#
# Exits non-zero on the first failure (CI-safe).
set -euo pipefail

ROOT="${1:?usage: verify_photos.sh <project-dir> [--wiring|--api|--web]}"
ONLY="${2:-}"
ROOT="$(cd "$ROOT" && pwd)"

step() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
want() { [[ -z "$ONLY" || "$ONLY" == "--$1" ]]; }
need() { # file, pattern, message
  if ! grep -q -- "$2" "$ROOT/$1" 2>/dev/null; then
    printf '\033[31m✗ %s\033[0m  (%s)\n' "$3" "$1"
    exit 1
  fi
}

if want wiring; then
  step "wiring"
  need api/app/schemas.py "class ImageInput" "API: ChatMessage has no images"
  need api/app/providers/ollama.py "def to_ollama_messages" "API: Ollama does not receive images"
  need api/app/providers/anthropic.py "def to_anthropic_turn" "API: Anthropic does not receive images"
  need api/app/providers/openai_compat.py "def to_openai_message" "API: OpenAI-compatible providers do not receive images"
  need api/app/services/chat.py "vision=vision" "API: chat does not route photos to vision models"
  need api/app/routes/models.py "image_limits" "API: /api/models has no image_limits"
  need api/app/main.py "BodySizeLimit" "API: no request size limit for /api/chat"
  need web/components/chat/composer.tsx 'aria-label="Add photos"' "web: composer has no Add photos button"
  need web/components/chat/chat-app.tsx "useAttachments" "web: chat-app does not manage photos"
  need web/hooks/use-chat.ts "toApiMessages" "web: use-chat does not send photos"
  need web/components/chat/message.tsx "PhotoGallery" "web: messages do not show photos"
  need web/components/chat/model-picker.tsx "Sees images" "web: model picker does not mark vision models"
  # The one rule that matters for safety: Ollama must get bytes, never strings.
  need api/app/providers/ollama.py "image.raw for image in m.images" "API: Ollama images must be raw bytes (strings are read as file paths)"
  echo "wiring looks complete"
fi

if want api; then
  step "api: uv sync"
  (cd "$ROOT/api" && uv sync --quiet)
  step "api: ruff"
  (cd "$ROOT/api" && uv run ruff check . && uv run ruff format --check .)
  step "api: pytest"
  (cd "$ROOT/api" && uv run pytest -q)
fi

if want web; then
  step "web: install"
  if [[ -d "$ROOT/web/node_modules/next" ]]; then
    echo "node_modules present"
  else
    (cd "$ROOT/web" && npm install --no-audit --no-fund)
  fi
  step "web: typecheck"
  (cd "$ROOT/web" && npm run typecheck)
  step "web: production build"
  (cd "$ROOT/web" && NEXT_TELEMETRY_DISABLED=1 npm run build)
fi

printf '\n\033[32m✓ Photo checks passed\033[0m\n'
