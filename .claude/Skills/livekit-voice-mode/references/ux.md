# Voice UX: states, copy, layout

The design follows the host chat UI: neutral tokens, no gradients, and no
decorative colour. The only accent is the emerald dot in the header timer.
Voice replaces the message list and composer in place: same page, same header,
same sidebar. It is not a separate route or a modal.

## Layout

```
┌ header ─────────────────────────────────────────── [● Voice 01:23] [✎] ┐
│                                                                        │
│   (captions on)  transcript: agent turns left, user bubbles right      │
│                  "Spoken" / "Listening…" under user turns              │
│                  "Speaking · <model>" / "Thinking…" under the agent    │
│   (captions off or no turns yet) centered intro: pulse mark + title    │
│                                                                        │
│   [banner: fallback notice or "Couldn't get a reply: …"]               │
│ ┌ voice bar ─────────────────────────────────────────────────────────┐ │
│ │ (mic)  status text + level bars       (⌄ settings)  [Stop]  [✕ End] │ │
│ └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

Mobile (390 px): the timer hides its "Voice" label, and the bar buttons
collapse to icons ("End" and "Stop" labels are `sm:` only).

## States (`VoiceUiState`)

| State | Bar | Intro title / subtitle |
|---|---|---|
| connecting | spinner · "Connecting…" · End | Connecting… / Setting up your voice session. |
| listening | mic · "Listening…" + mic level bars · settings · End | I'm listening / Start speaking. I'll reply when you pause. |
| thinking | mic · "Thinking" + blinking dots · settings · **Stop** · End | Thinking… / Working on a reply. |
| speaking | mic · "Speaking… talk anytime to interrupt" · settings · **Stop** · End | Speaking… / Talk anytime to interrupt. |
| muted (any live state) | filled mic-off · "Microphone off — Tap the mic to unmute" | (unchanged) |
| reconnecting | spinning arrows · "Connection lost. Reconnecting…" · End | Reconnecting… / Your connection dropped. Trying again. |
| mic-blocked | alert · "Microphone access is blocked" + reason · Type instead · Try again | Microphone needed / Voice mode needs access to your microphone. |
| failed | alert · "Voice mode couldn't start" + reason · Type instead · Try again | Voice mode is unavailable / See the message below. |
| ended | alert (muted) · "The voice session ended" · Type instead · Try again | Session ended / Start again or go back to typing. |

Specific mic messages:

- No microphone was found. Connect one and try again.
- Your microphone is being used by another app.
- Allow microphone access in your browser's site settings, then try again.

Agent failure: `<SDK reason or "The voice agent didn't join."> Make sure the agent is running and uses the same LiveKit project.`

Banners (above the bar):

- Fallback: `Using <provider> because the selected model was unavailable (<notice>).`
- Reply error: `Couldn't get a reply: <reason>`. The agent also says a short
  apology aloud.

## Settings menu (chevron in the bar)

- **Microphone**: live device list (`useMediaDeviceSelect`), switching
  without reconnecting.
- **Voice · applies to your next session**: shown only when `VOICE_VOICES` is
  set. The TTS voice is fixed at dispatch time, hence the label.
- **Live captions**: on shows the transcript; off shows the centered intro
  only. Both prefs persist per browser.

## Accessibility

- The bar is `role="group"` "Voice controls", and the status text is
  `role="status"`, so state changes are announced. Failures use
  `role="alert"`.
- The timer has `role="timer"` with a spoken label ("Voice session, 01 minutes
  23 seconds").
- The mute button uses `aria-pressed`. Every icon button has an `aria-label`
  ("Start voice mode", "Mute microphone", "Stop the reply", "End voice mode",
  "Voice settings"). The e2e test selects by these labels, so keep them stable.
- Animations use `motion-safe:`, so reduced-motion users get static
  indicators.
- Keyboard: Esc stops a reply (not while a menu is open). All controls are
  reachable by Tab.

## After the session

Transcripts are already in the chat: user turns tagged "Spoken", assistant
turns with the model under them, and the sidebar entry carrying the
sound-wave icon. The composer returns and shows the voice button again, so
typing and talking can alternate in one conversation. Each voice session
starts with the chat's recent history.
