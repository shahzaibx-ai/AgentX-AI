"""Anchored edits that wire voice mode into the fullstack-ai-assistant template.

Generated from the verified pre-voice and voice versions of each file.
Each edit replaces OLD (which must appear exactly once) with NEW. An edit whose
NEW text is already present counts as applied, so the installer is idempotent.
"""

EDITS: list[tuple[str, str, str]] = [
    # ---- api/app/main.py
    (
        'api/app/main.py',
        '''from app.routes import chat, health, models

''',
        '''from app.routes import chat, health, models
from app.voice import VoiceSettings, mount_voice
from app.voice_brain import chat_brain

''',
    ),
    # ---- api/app/main.py
    (
        'api/app/main.py',
        '''def create_app(
    settings: Settings | None = None, registry: ProviderRegistry | None = None
) -> FastAPI:
''',
        '''def create_app(
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
    voice_settings: VoiceSettings | None = None,
) -> FastAPI:
''',
    ),
    # ---- api/app/main.py
    (
        'api/app/main.py',
        '''        app.include_router(router, prefix="/api")
    return app
''',
        '''        app.include_router(router, prefix="/api")
    mount_voice(app, brain=chat_brain, settings=voice_settings)  # voice mode (LiveKit)
    return app
''',
    ),
    # ---- api/.env.example
    (
        'api/.env.example',
        '''META_MODEL=
''',
        '''META_MODEL=

# ---------- Voice mode (LiveKit) ----------
# Voice is enabled when all three are set. Use the same project as the agent.
# LIVEKIT_URL must be reachable from the browser (e.g. wss://<project>.livekit.cloud).
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
# Must match VOICE_AGENT_NAME in agent/.env
VOICE_AGENT_NAME=my-agent
# Shared secret the agent sends to /api/voice/chat (same value in agent/.env). Empty = off.
# Set it whenever the API is reachable from the internet:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
VOICE_AGENT_TOKEN=
# Optional voice picker (ids passed to the agent's TTS). Leave [] to use the agent default.
# VOICE_VOICES=[{"id":"calm","name":"Calm","description":"Even and relaxed","tts_voice":"<tts voice id>"}]
VOICE_VOICES=[]
''',
    ),
    # ---- docker-compose.yml
    (
        'docker-compose.yml',
        '''
  # Optional: run Ollama in Docker instead of on the host.
''',
        '''
  # Voice mode (LiveKit). Start with:  docker compose --profile voice up --build
  # Needs LIVEKIT_* in both api/.env and agent/.env (same LiveKit Cloud project).
  agent:
    build: ./agent
    profiles: ["voice"]
    env_file:
      - path: ./agent/.env
        required: false
    environment:
      API_URL: http://api:8000
    depends_on:
      - api
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8081/')"]
      interval: 30s
      timeout: 3s
      start_period: 20s
    restart: unless-stopped

  # Optional: run Ollama in Docker instead of on the host.
''',
    ),
    # ---- web/lib/types.ts
    (
        'web/lib/types.ts',
        '''  feedback?: "up" | "down" | null;
}
''',
        '''  feedback?: "up" | "down" | null;
  /** Spoken in voice mode (transcript) rather than typed. */
  voice?: boolean;
}
''',
    ),
    # ---- web/hooks/use-chat.ts
    (
        'web/hooks/use-chat.ts',
        '''
  const clearAll = useCallback(() => {
''',
        '''
  /**
   * Saves voice transcripts. A message whose id is already in the chat is
   * updated (late words); others are appended. With no conversation yet,
   * creates one (titled from the first spoken user message), opens it, and
   * returns its id so later transcripts from the same session land there.
   */
  const appendVoiceMessages = useCallback(
    (conversationId: string | null, messages: ChatMessage[]): string => {
      const now = Date.now();
      if (conversationId) {
        update(conversationId, (c) => {
          const byId = new Map(messages.map((m) => [m.id, m]));
          const updated = c.messages.map((m) => {
            const next = byId.get(m.id);
            if (!next) return m;
            byId.delete(m.id);
            return { ...m, content: next.content, meta: next.meta ?? m.meta };
          });
          return { ...c, messages: [...updated, ...byId.values()], updatedAt: now };
        });
        return conversationId;
      }
      const id = uid();
      const firstUser = messages.find((m) => m.role === "user");
      setConversations((list) => [
        {
          id,
          title: makeTitle(firstUser?.content ?? "Voice chat"),
          messages,
          createdAt: now,
          updatedAt: now,
        },
        ...list,
      ]);
      setActiveId(id);
      return id;
    },
    [update],
  );

  const clearAll = useCallback(() => {
''',
    ),
    # ---- web/hooks/use-chat.ts
    (
        'web/hooks/use-chat.ts',
        '''    clearAll,
  };
''',
        '''    clearAll,
    appendVoiceMessages,
  };
''',
    ),
    # ---- web/components/chat/composer.tsx
    (
        'web/components/chat/composer.tsx',
        '''import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUpIcon, SquareIcon } from "lucide-react";

''',
        '''import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUpIcon, AudioLinesIcon, SquareIcon } from "lucide-react";

''',
    ),
    # ---- web/components/chat/composer.tsx
    (
        'web/components/chat/composer.tsx',
        '''import { Button } from "@/components/ui/button";
import { APP_CONFIG } from "@/lib/config";
''',
        '''import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { APP_CONFIG } from "@/lib/config";
''',
    ),
    # ---- web/components/chat/composer.tsx
    (
        'web/components/chat/composer.tsx',
        '''  onStop,
  streaming,
''',
        '''  onStop,
  onVoice,
  streaming,
''',
    ),
    # ---- web/components/chat/composer.tsx
    (
        'web/components/chat/composer.tsx',
        '''  onStop: () => void;
  streaming: boolean;
''',
        '''  onStop: () => void;
  /** When set, an empty composer shows a "Start voice mode" button instead of Send. */
  onVoice?: () => void;
  streaming: boolean;
''',
    ),
    # ---- web/components/chat/composer.tsx
    (
        'web/components/chat/composer.tsx',
        '''  const canSend = streaming || (!!value.trim() && !disabled);

''',
        '''  const canSend = streaming || (!!value.trim() && !disabled);
  const showVoice = !!onVoice && !streaming && !value.trim();

''',
    ),
    # ---- web/components/chat/composer.tsx
    (
        'web/components/chat/composer.tsx',
        '''      <div className="mt-1 flex items-center justify-end">
        <Button
          type="submit"
          size="icon"
          disabled={!canSend}
          aria-label={streaming ? "Stop generating" : "Send message"}
          className={cn("rounded-full", !canSend && "opacity-30")}
        >
          {streaming ? <SquareIcon className="size-3.5 fill-current" /> : <ArrowUpIcon />}
        </Button>
      </div>
''',
        '''      <div className="mt-1 flex items-center justify-end">
        {showVoice ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                onClick={onVoice}
                aria-label="Start voice mode"
                className="rounded-full"
              >
                <AudioLinesIcon />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Start voice mode</TooltipContent>
          </Tooltip>
        ) : (
          <Button
            type="submit"
            size="icon"
            disabled={!canSend}
            aria-label={streaming ? "Stop generating" : "Send message"}
            className={cn("rounded-full", !canSend && "opacity-30")}
          >
            {streaming ? <SquareIcon className="size-3.5 fill-current" /> : <ArrowUpIcon />}
          </Button>
        )}
      </div>
''',
    ),
    # ---- web/components/chat/message.tsx
    (
        'web/components/chat/message.tsx',
        '''  HardDriveIcon,
  CloudIcon,
''',
        '''  HardDriveIcon,
  MicIcon,
  CloudIcon,
''',
    ),
    # ---- web/components/chat/message.tsx
    (
        'web/components/chat/message.tsx',
        '''        </div>
        <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
          <CopyAction text={message.content} />
        </div>
''',
        '''        </div>
        <div className="flex items-center gap-1">
          {message.voice && (
            <span className="flex items-center gap-1 px-1 text-xs text-muted-foreground">
              <MicIcon className="size-3" />
              Spoken
            </span>
          )}
          <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
            <CopyAction text={message.content} />
          </div>
        </div>
''',
    ),
    # ---- web/components/chat/app-sidebar.tsx
    (
        'web/components/chat/app-sidebar.tsx',
        '''import {
  CheckIcon,
''',
        '''import {
  AudioLinesIcon,
  CheckIcon,
''',
    ),
    # ---- web/components/chat/app-sidebar.tsx
    (
        'web/components/chat/app-sidebar.tsx',
        '''                      className={cn(
                        "w-full truncate rounded-md py-1.5 pr-9 pl-3 text-left text-sm transition-colors hover:bg-sidebar-accent",
                        active && "bg-sidebar-accent font-medium",
''',
        '''                      className={cn(
                        "flex w-full items-center gap-2 rounded-md py-1.5 pr-9 pl-3 text-left text-sm transition-colors hover:bg-sidebar-accent",
                        active && "bg-sidebar-accent font-medium",
''',
    ),
    # ---- web/components/chat/app-sidebar.tsx
    (
        'web/components/chat/app-sidebar.tsx',
        '''                    >
                      {c.title}
                    </button>
''',
        '''                    >
                      {c.messages.some((m) => m.voice) && (
                        <AudioLinesIcon
                          aria-label="Voice chat"
                          className="size-3.5 shrink-0 text-muted-foreground"
                        />
                      )}
                      <span className="truncate">{c.title}</span>
                    </button>
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''
import { useCallback, useEffect, useState } from "react";
import { PanelLeftIcon, SquarePenIcon } from "lucide-react";
''',
        '''
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { PanelLeftIcon, SquarePenIcon } from "lucide-react";
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''import { EmptyState, SuggestionGrid } from "@/components/chat/empty-state";
import { MessageList } from "@/components/chat/message-list";
''',
        '''import { EmptyState, SuggestionGrid } from "@/components/chat/empty-state";
import { Markdown } from "@/components/chat/markdown";
import { MessageList } from "@/components/chat/message-list";
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useChat } from "@/hooks/use-chat";
''',
        '''import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { VoiceLoading, VoiceTimer } from "@/components/voice/voice-chrome";
import { useChat } from "@/hooks/use-chat";
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''import { useModels } from "@/hooks/use-models";
import { cn } from "@/lib/utils";
''',
        '''import { useModels } from "@/hooks/use-models";
import { useVoiceConfig } from "@/hooks/use-voice-config";
import { APP_CONFIG } from "@/lib/config";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''import { cn } from "@/lib/utils";

''',
        '''import { cn } from "@/lib/utils";

// LiveKit is only downloaded when someone starts voice mode.
const VoiceSession = dynamic(() => import("@/components/voice/voice-session"), {
  ssr: false,
  loading: () => <VoiceLoading />,
});

const renderMarkdown = (text: string) => <Markdown content={text} />;

interface ActiveVoice {
  key: number;
  startedAt: number;
  history: ChatMessage[];
}

''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''  const chat = useChat(models.selection);
  const [sidebarOpen, setSidebarOpen] = useState(true); // desktop
''',
        '''  const chat = useChat(models.selection);
  const voiceSetup = useVoiceConfig();
  const [sidebarOpen, setSidebarOpen] = useState(true); // desktop
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''  const [mobileOpen, setMobileOpen] = useState(false); // mobile sheet

''',
        '''  const [mobileOpen, setMobileOpen] = useState(false); // mobile sheet
  const [voice, setVoice] = useState<ActiveVoice | null>(null);

''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''  const noModels = !models.loading && !models.effective;

''',
        '''  const noModels = !models.loading && !models.effective;
  const voiceEnabled = !!voiceSetup.config?.enabled && !noModels;

''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''
  const newChat = useCallback(() => {
''',
        '''
  // ---- voice mode ----
  // Transcripts go into the chat that was open when voice started, or into a
  // new chat created on the first thing the user says.
  const voiceConversation = useRef<string | null>(null);
  const voiceBuffer = useRef<ChatMessage[]>([]);
  const appendVoice = chat.appendVoiceMessages;

  const startVoice = useCallback(() => {
    if (chat.streaming) chat.stop();
    const current = chat.active && chat.active.messages.length ? chat.active : null;
    voiceConversation.current = current?.id ?? null;
    voiceBuffer.current = [];
    setVoice({ key: Date.now(), startedAt: Date.now(), history: current?.messages ?? [] });
    setMobileOpen(false);
  }, [chat]);

  const endVoice = useCallback(() => setVoice(null), []);
  const retryVoice = useCallback(
    () => setVoice((v) => (v ? { ...v, key: v.key + 1, startedAt: Date.now() } : v)),
    [],
  );

  const saveTranscripts = useCallback(
    (batch: ChatMessage[]) => {
      // Merge by id: a later batch may carry updated text for a buffered message.
      const merged = new Map(voiceBuffer.current.map((m) => [m.id, m]));
      for (const m of batch) merged.set(m.id, m);
      const all = [...merged.values()];
      // Don't create a chat for a greeting nobody answered.
      if (!voiceConversation.current && !all.some((m) => m.role === "user")) {
        voiceBuffer.current = all;
        return;
      }
      voiceBuffer.current = [];
      voiceConversation.current = appendVoice(voiceConversation.current, all);
    },
    [appendVoice],
  );

  // ---- navigation (ends voice mode first) ----
  const newChat = useCallback(() => {
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''  const newChat = useCallback(() => {
    chat.newChat();
''',
        '''  const newChat = useCallback(() => {
    setVoice(null);
    chat.newChat();
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''  const openChat = (id: string) => {
    chat.openChat(id);
''',
        '''  const openChat = (id: string) => {
    if (voice && id !== voiceConversation.current) setVoice(null);
    chat.openChat(id);
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''  const deleteChat = (id: string) => {
    const undo = chat.deleteChat(id);
''',
        '''  const deleteChat = (id: string) => {
    if (voice && id === voiceConversation.current) setVoice(null);
    const undo = chat.deleteChat(id);
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''  const clearAll = () => {
    const undo = chat.clearAll();
''',
        '''  const clearAll = () => {
    setVoice(null);
    const undo = chat.clearAll();
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''
  // Global shortcuts: new chat, search, stop.
  useEffect(() => {
''',
        '''
  // Global shortcuts: new chat, search, stop. (Voice mode handles its own Esc.)
  useEffect(() => {
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''      onStop={chat.stop}
      streaming={chat.streaming}
''',
        '''      onStop={chat.stop}
      onVoice={voiceEnabled ? startVoice : undefined}
      streaming={chat.streaming}
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''          <div className="flex-1" />
          <Tooltip>
''',
        '''          <div className="flex-1" />
          {voice && <VoiceTimer startedAt={voice.startedAt} />}
          <Tooltip>
''',
    ),
    # ---- web/components/chat/chat-app.tsx
    (
        'web/components/chat/chat-app.tsx',
        '''
        {empty ? (
          <div className="flex flex-1 flex-col justify-center overflow-y-auto px-3 pb-[8vh] sm:px-6">
''',
        '''
        {voice ? (
          <VoiceSession
            key={voice.key}
            selection={models.selection}
            participantName={APP_CONFIG.user.name}
            history={voice.history}
            voices={voiceSetup.config?.voices ?? []}
            voice={voiceSetup.prefs.voice}
            captions={voiceSetup.prefs.captions}
            onPrefsChange={voiceSetup.setPrefs}
            onTranscripts={saveTranscripts}
            onEnd={endVoice}
            onRetry={retryVoice}
            renderText={renderMarkdown}
          />
        ) : empty ? (
          <div className="flex flex-1 flex-col justify-center overflow-y-auto px-3 pb-[8vh] sm:px-6">
''',
    ),
]
