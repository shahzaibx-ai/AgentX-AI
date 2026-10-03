---
name: livekit-voice-mode
description: Add a production-ready, Claude/ChatGPT-style voice mode to an AI chat app using LiveKit. It covers a LiveKit Agents voice worker (LiveKit Inference STT/TTS/turn detection, ai-coustics noise cancellation, interrupt RPC, never-silent failures) whose replies come from the app's own chat backend. The backend side is a portable FastAPI voice package (room tokens with agent dispatch, per-room model/history context, SSE brain endpoint, optional agent token). The frontend is a Next.js/React voice UI (voice button in the composer, live transcript, all connection/mic/error states, stop/mute/end, device and voice settings, transcripts saved into the chat). Use whenever the user wants to add voice mode, a voice agent, speech-to-speech, "talk to the assistant", or a LiveKit agent to a chat app or a fullstack-ai-assistant project, or wants to customise, test, deploy, secure or debug such a voice feature (agent not joining, no voice button, silent replies, transcripts not saved).
---

# LiveKit voice mode

A complete, tested voice feature you can drop into a chat app. The user talks,
the agent answers with the **same model and fallback as typed chat**, and the
conversation is saved into the chat with typed and spoken turns mixed.

```
Browser ──POST /api/voice/session──► API: room + token that dispatches the agent
   │                                     (remembers the chosen model + chat history)
   └──WebRTC (mic/speaker)──► LiveKit ◄── agent: STT → turn detection → reply → TTS
                                               │
                                  POST /api/voice/chat ──► your chat pipeline (the "brain")
```

Verified September 2026: livekit-agents 1.8.3, livekit-api 1.2.1,
livekit-client 2.22.3, @livekit/components-react 2.9.24, Next.js 16,
React 19, FastAPI, Python 3.13. On a pre-voice fullstack-ai-assistant project,
the installer's result is byte-identical to the hand-verified reference. That
result passes 39 API tests, 13 agent tests, the typecheck and the production
build, plus a live browser test (desktop, mobile, dark) against a real LiveKit
server with the agent token on.

## Workflow

### 1. Identify the target

| Project | Path |
|---|---|
| Built from the **fullstack-ai-assistant** template (`api/app/main.py` has `create_app`, `web/components/chat/chat-app.tsx` exists) | Run the installer (step 2) |
| Other FastAPI backend | `references/integrate-fastapi.md`: copy the package, write a brain, call `mount_voice` |
| Other Next.js / React frontend | `references/integrate-nextjs.md`: copy the voice components, add a start button, save transcripts |
| Other backend language / frontend framework | Keep `agent/` as is; implement the three endpoints from `references/architecture.md` |

Ask at most one question, and only if it changes the build (for example, "Is
the API reachable from the internet?" → then the agent token is needed now).
The placeholder user name is **Rizwan**.

### 2. Install (template projects)

```bash
python <skill>/scripts/install_voice.py --project <app> --dry-run   # preview
python <skill>/scripts/install_voice.py --project <app>             # install
```

Safe to re-run. It:
- copies `agent/` and the self-contained API and web files;
- adds the dependencies and runs `uv sync` (api, agent) and `npm install`
  (web);
- applies 36 anchored edits to the 9 files that wire voice in;
- adds the env blocks and a README section;
- renames the agent package to match the project.

A file that was customised so that an edit's anchor no longer matches is
**left unchanged** and reported with its edit numbers. Make those edits by
hand from `references/manual-edits.md`, or rerun with `--partial`. Exit code 1
means manual steps remain. Don't recreate the voice code from memory; the
assets encode many non-obvious LiveKit fixes (`references/troubleshooting.md`).

### 3. Configure

Put **the same** `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` in
`api/.env` and `agent/.env`, from a LiveKit Cloud project (Inference speech and
noise cancellation need Cloud). Keep `VOICE_AGENT_NAME` equal on both sides.
Set `VOICE_AGENT_TOKEN` on both sides whenever the API is public. Details:
`references/configuration.md`, and `references/agent.md` for models, voices,
language, greeting and instructions.

```bash
python <skill>/scripts/doctor_voice.py --project <app>          # config consistency
python <skill>/scripts/doctor_voice.py --project <app> --live   # + running API, token, agent
```

### 4. Verify (always, before delivering)

```bash
bash <skill>/scripts/verify_voice.sh <app>     # wiring + ruff/pytest (api, agent) + typecheck/build (web)
```

For a live test without LiveKit Cloud, use the local LiveKit server, the
stand-in Ollama and the agent harness (real agent code, fake STT/TTS), then:

```bash
BASE_URL=http://localhost:3000 node <skill>/assets/testing/voice_e2e.js all
```

The full procedure and the failure paths to check are in
`references/testing.md`. Look at the screenshots.

### 5. Deliver

Report what was installed, which checks passed (with numbers), and what could
not be tested here (real LiveKit Cloud speech, a real microphone). Give the run
commands:

```bash
cd api   && uv run fastapi dev app/main.py
cd web   && npm run dev
cd agent && uv run python voice_agent.py download-files && uv run python voice_agent.py dev
# Docker: docker compose --profile voice up --build
```

## Rules that keep voice reliable

- **Brain contract.** The API side calls one function: `brain(request, BrainRequest) → async (event, data)`
  with events `meta` / `delta` / `error` / `done`. Keep host-app logic in the
  brain adapter (`api/app/voice_brain.py`), never inside `app/voice/`.
- **The agent needs a real `llm.LLM`** (`AppLLM`). The session skips replies
  when `llm` is None, even if `llm_node` is overridden.
- **Never silent.** Every failure is spoken (`FALLBACK_REPLY`) and shown
  (`assistant.error`). New code paths need a test for their failure.
- **Voice replies are spoken text.** Keep the voice instructions as the first
  system message; keep the TTS markdown and emoji filters.
- **Transcripts:** save in spoken order, with stable ids `voice-<segment id>`,
  and **upsert**. Agent turns count as final when the agent goes idle. Buffer
  until the first user message.
- **React:** start in a 0 ms timer and end in cleanup (Strict Mode); load
  `VoiceSession` with `next/dynamic` and `ssr:false`.
- **Esc** stops the reply, except inside menus or dialogs. **Stop** is the
  `interrupt` RPC.
- **No voice UI without config:** the button only appears when
  `/api/voice/config` says `enabled`.
- **Security:** put `/api/voice/session` behind login; set
  `VOICE_AGENT_TOKEN` when the API is public (`references/deployment.md`).
- **Design:** neutral shadcn tokens, no gradients. Voice replaces the message
  list in place. Keep the aria-labels (the e2e test uses them).

## References

| Need | Read |
|---|---|
| How it fits together, endpoints, SSE, brain, attributes, RPC | `references/architecture.md` |
| Wire into FastAPI / write a brain for another stack / Redis context | `references/integrate-fastapi.md` |
| Wire into Next.js or React, `VoiceSession` props, UI behaviour rules | `references/integrate-nextjs.md` |
| Exact edits the installer makes (numbered) | `references/manual-edits.md` |
| Env vars and the rules tying them together | `references/configuration.md` |
| Agent: models, voices, language, tools, self-hosted LiveKit, push-to-talk | `references/agent.md` |
| States, copy, layout, accessibility | `references/ux.md` |
| Unit and end-to-end testing | `references/testing.md` |
| Docker, agent hosting, auth, scaling, costs | `references/deployment.md` |
| Symptom → cause → fix | `references/troubleshooting.md` |

## Contents

```
scripts/install_voice.py        installer (stdlib; --dry-run, --no-install, --force, --partial, --skip)
scripts/patches.py              the 36 anchored edits (generated)
scripts/doctor_voice.py         config + live checks with fixes (stdlib)
scripts/verify_voice.sh         wiring + quality gates (CI-safe)
scripts/maintain/               regenerate patches.py and manual-edits.md after changing the template
assets/agent/                   LiveKit Agents worker (uv project, tests, Dockerfile)
assets/api/app/voice/           portable FastAPI voice package (+ voice_brain.py adapter, tests)
assets/web/                     lib/voice.ts, hooks/use-voice-config.ts, components/voice/*
assets/testing/                 fake_ollama.py, voice_e2e_agent.py (fake STT/TTS), voice_e2e.js (browser test)
```

When the template's voice code changes, update `assets/`, then regenerate the
edits: `python scripts/maintain/make_patches.py <pre-voice-project> <voice-project> scripts/patches.py`
and `python scripts/maintain/render_manual_edits.py`. Re-test the installer on
a pre-voice copy (the result should match the voice project byte for byte).
