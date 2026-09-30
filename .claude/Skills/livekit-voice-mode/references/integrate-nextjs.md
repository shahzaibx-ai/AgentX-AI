# Integrating the web side

## Files (copied as-is)

| File | Job |
|---|---|
| `lib/voice.ts` | Types, `fetchVoiceConfig`, `createVoiceSession`, agent attribute names. `API_BASE` = `NEXT_PUBLIC_API_BASE ?? "/api"` |
| `hooks/use-voice-config.ts` | Loads `/api/voice/config` once; per-browser prefs (`voice`, `captions`) in localStorage key `assistant.voice.v1` |
| `components/voice/voice-session.tsx` | **Default export**: the whole voice screen for one session: LiveKit session, transcript, saving, errors |
| `components/voice/voice-bar.tsx` | The pill-shaped control bar and every state; settings menu (mic, voice, captions) |
| `components/voice/level-bars.tsx` | Mic level bars (`useMultibandTrackVolume`, 5 bands) and the agent's pulsing mark |
| `components/voice/voice-chrome.tsx` | `VoiceTimer` (header pill) and `VoiceLoading` (while the chunk downloads) |
| `components/voice/voice.css` | Keyframes `voice-pulse`, `voice-blink`, `voice-caret`, imported by voice-session |

Dependencies: `livekit-client@^2.22.3`, `@livekit/components-react@^2.9.24`,
plus these from the shadcn/ui stack: `components/ui/button`,
`components/ui/dropdown-menu`, `lucide-react`, `sonner` (toasts), `cn` from
`lib/utils`, and the shadcn colour tokens (`bg-card`, `text-muted-foreground`,
`destructive`, …). Any shadcn/ui + Tailwind 4 app has all of these; otherwise
run `npx shadcn@latest add button dropdown-menu sonner`.

## `VoiceSession` props

```tsx
<VoiceSession
  key={voice.key}                        // bump to retry with a fresh room
  selection={models.selection}           // {provider, model} | null (auto)
  participantName="Rizwan"               // shown to the agent
  history={messages}                     // [{role, content}] of the open chat (API keeps the last N)
  voices={config.voices}                 // from /api/voice/config; [] hides the picker
  voice={prefs.voice}  captions={prefs.captions}
  onPrefsChange={setPrefs}               // ({voice?, captions?}) => void
  onTranscripts={save}                   // (VoiceTranscript[]) => void, spoken order, upsert by id
  onEnd={() => setVoice(null)}
  onRetry={() => setVoice(v => ({...v, key: v.key + 1}))}
  renderText={(t) => <Markdown content={t} />}   // optional; default plain text
/>
```

`VoiceTranscript` is `{id: "voice-<segment id>", role, content, createdAt, voice: true, meta?}`.
The same id can arrive again with longer text, so **upsert by id**. Never append
twice.

Load it only when needed, so LiveKit isn't in the main bundle:

```tsx
const VoiceSession = dynamic(() => import("@/components/voice/voice-session"), {
  ssr: false,
  loading: () => <VoiceLoading />,
});
```

## Wiring in the template (what the installer's edits do)

- **`lib/types.ts`**: `ChatMessage.voice?: boolean`.
- **`hooks/use-chat.ts`**: `appendVoiceMessages(conversationId | null, messages) → id`.
  It upserts into an existing chat. With `null`, it creates a chat titled from
  the first spoken user message, opens it, and returns the id so later batches
  land in the same chat.
- **`components/chat/composer.tsx`**: an `onVoice?` prop. When set, and the box
  is empty and nothing is streaming, the Send button becomes an AudioLines
  **Start voice mode** button with a tooltip. Typing turns it back into Send.
- **`components/chat/chat-app.tsx`**:
  - `useVoiceConfig()`; `voiceEnabled = config.enabled && a model exists`.
  - `voice` state `{key, startedAt, history}`. **Start** stops any typed stream,
    remembers the open chat (`voiceConversation` ref), and snapshots its
    messages as history.
  - `saveTranscripts` buffers until the first user message, so an unanswered
    greeting creates no chat. It merges batches by id, then calls
    `appendVoiceMessages`.
  - Navigation ends voice first: New chat, Clear all, opening another chat, or
    deleting the voice chat.
  - The header shows `<VoiceTimer>`; the main area renders `<VoiceSession>`
    in place of the message list.
- **`components/chat/message.tsx`**: a "Spoken" tag with a mic icon under user messages with
  `voice: true`.
- **`components/chat/app-sidebar.tsx`**: an AudioLines icon before the titles
  of chats that contain voice messages.

Exact diffs: `manual-edits.md`.

## Another Next.js / React app

1. Copy the files above; install the two LiveKit packages; make sure the
   shadcn primitives exist.
2. Proxy `/api` to the API (Next `rewrites`), or set
   `NEXT_PUBLIC_API_BASE=https://api.example.com/api`. For cross-origin, allow
   the web origin in the API's CORS settings.
3. Add a voice entry point where users start voice (a button in your input
   box). Show it only when `useVoiceConfig().config?.enabled`.
4. Render `VoiceSession` in place of your message list while voice is active,
   and save `onTranscripts` into your message store with upsert by id.
5. Plain React (Vite): remove `"use client"` if you like, and replace
   `next/dynamic` with `React.lazy` + `Suspense`.

Non-React frontends: keep the API and the agent, and build the client with
`livekit-client` directly. Flow: `POST /api/voice/session` → `room.connect(server_url, participant_token)`
→ publish the mic → play the agent's audio track → read the
`lk.transcription` text streams and the agent's participant attributes → call the
`interrupt` RPC for Stop.

## Behaviour rules (keep them when you change the UI)

- Start in a 0 ms timer and end in cleanup, for React Strict Mode (see
  `architecture.md`).
- Esc = Stop, except when the event comes from an open menu, dialog or
  listbox, or was already `defaultPrevented`. Otherwise closing the settings
  menu cuts the reply.
- Stop = the `interrupt` RPC to the agent. Mute =
  `localParticipant.setMicrophoneEnabled(!enabled)`.
- An agent reply counts as finished when the agent stops speaking or thinking
  (its final flag never reaches the client). User segments are final on
  `lk.transcription_final === "true"`, or when a newer user segment supersedes
  them.
- Save in spoken order: stop at the first unfinished segment. Flush whatever is
  left on unmount.
- The live view strips a trailing unclosed code fence
  (`/\n?```[\w+#.-]*\s*$/`), so an interrupted reply doesn't render an empty
  code block.
- Level bars use the default bands (about 2–14 kHz); custom `loPass`/`hiPass`
  values flattened them in testing.
- After 20 s without the agent (`agentConnectTimeoutMilliseconds`), show
  "Voice mode couldn't start" + "Make sure the agent is running…" with **Try
  again** / **Type instead**.
- Mic errors: `SessionEvent.MediaDevicesError`, or `start()` rejecting with
  `NotAllowedError` / `NotFoundError` / `NotReadableError`, show the
  mic-blocked state with a specific message.

States and copy are listed in `ux.md`.
