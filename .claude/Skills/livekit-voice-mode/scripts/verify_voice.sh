#!/usr/bin/env bash
# Quality gates for a project with voice mode installed.
#
#   bash verify_voice.sh <project-dir>            # wiring + api + agent + web
#   bash verify_voice.sh <project-dir> --api      # or --agent / --web / --wiring
#
# Exits non-zero on the first failure (CI-safe).
set -euo pipefail

ROOT="${1:?usage: verify_voice.sh <project-dir> [--wiring|--api|--agent|--web]}"
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
  need api/app/main.py "mount_voice(" "API: mount_voice(app, brain=...) is not called"
  need api/pyproject.toml "livekit-api" "API: livekit-api dependency missing"
  need web/package.json '"livekit-client"' "web: livekit-client dependency missing"
  need web/package.json '"@livekit/components-react"' "web: @livekit/components-react dependency missing"
  need web/components/chat/composer.tsx 'aria-label="Start voice mode"' "web: composer has no Start voice mode button"
  need web/components/chat/chat-app.tsx "components/voice/voice-session" "web: chat-app does not load VoiceSession"
  need web/hooks/use-chat.ts "appendVoiceMessages" "web: use-chat cannot save transcripts"
  need agent/voice_agent.py "rtc_session" "agent/voice_agent.py missing"
  echo "wiring looks complete"
fi

python_gates() {
  local name="$1"
  step "$name: uv sync"
  (cd "$ROOT/$name" && uv sync --quiet)
  step "$name: ruff"
  (cd "$ROOT/$name" && uv run ruff check . && uv run ruff format --check .)
  step "$name: pytest"
  (cd "$ROOT/$name" && uv run pytest -q)
}

want api && python_gates api
want agent && python_gates agent

if want web; then
  step "web: install"
  if [[ -d "$ROOT/web/node_modules/livekit-client" ]]; then
    echo "node_modules present"
  else
    (cd "$ROOT/web" && npm install --no-audit --no-fund)
  fi
  step "web: typecheck"
  (cd "$ROOT/web" && npm run typecheck)
  step "web: production build"
  (cd "$ROOT/web" && NEXT_TELEMETRY_DISABLED=1 npm run build)
fi

printf '\n\033[32m✓ Voice checks passed\033[0m\n'
