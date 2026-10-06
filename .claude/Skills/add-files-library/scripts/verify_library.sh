#!/usr/bin/env bash
# Quality gates for a project with "Add files" and the Library installed.
#
#   bash verify_library.sh <project-dir>            # wiring + api + web
#   bash verify_library.sh <project-dir> --api      # or --web / --wiring
#
# Exits non-zero on the first failure (CI-safe).
set -euo pipefail

ROOT="${1:?usage: verify_library.sh <project-dir> [--wiring|--api|--web]}"
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
  need api/pyproject.toml "google-genai" "API: google-genai is not a dependency"
  need api/app/main.py "mount_library" "API: the Library is not mounted"
  need api/app/main.py '"/api/files"' "API: no upload size limit for /api/files"
  need api/app/schemas.py "class RagScope" "API: chat requests can't carry rag"
  need api/app/schemas.py "chat_id" "API: RagScope has no chat_id (file isolation)"
  need api/app/routes/chat.py "rag_chat_events" "API: chat does not answer from documents"
  need api/app/library/service.py "def resolve_scope" "API: old library package (no scope resolution)"
  need web/next.config.ts "proxyClientMaxBodySize" "web: uploads over 10 MB fail through the /api rewrite"
  need web/lib/api.ts '"sources"' "web: the sources event is ignored"
  need web/hooks/use-chat.ts "chat_id: chatId" "web: questions don't say which chat their files belong to"
  need web/hooks/use-chat-files.ts "reused" "web: removing a re-added file can delete an earlier message's copy"
  need web/components/chat/composer.tsx "Search Library" "web: composer has no Search Library menu"
  need web/components/chat/chat-app.tsx "useChatFiles" "web: chat-app does not manage files"
  need web/components/chat/message.tsx "SourcesList" "web: answers don't show sources"
  need web/components/chat/app-sidebar.tsx 'href="/library"' "web: no link to the Library pages"
  # Safety: uploaded files must never be served as active content.
  need api/app/library/routes.py "sandbox; default-src 'none'" "API: originals are served without a sandbox CSP"
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

printf '\n\033[32m✓ Library checks passed\033[0m\n'
