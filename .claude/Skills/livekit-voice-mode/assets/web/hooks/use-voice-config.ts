"use client";

import { useEffect, useState } from "react";

import { fetchVoiceConfig, type VoiceConfig } from "@/lib/voice";

const PREFS_KEY = "assistant.voice.v1";

export interface VoicePrefs {
  voice: string | null;
  captions: boolean;
}

const DEFAULT_PREFS: VoicePrefs = { voice: null, captions: true };

function loadPrefs(): VoicePrefs {
  try {
    const raw = window.localStorage.getItem(PREFS_KEY);
    return { ...DEFAULT_PREFS, ...(raw ? (JSON.parse(raw) as Partial<VoicePrefs>) : {}) };
  } catch {
    return DEFAULT_PREFS;
  }
}

function savePrefs(prefs: VoicePrefs) {
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable: keep in memory */
  }
}

/** Server voice availability plus the user's voice preferences (saved in the browser). */
export function useVoiceConfig() {
  const [config, setConfig] = useState<VoiceConfig | null>(null);
  const [prefs, setPrefsState] = useState<VoicePrefs>(DEFAULT_PREFS);

  useEffect(() => {
    setPrefsState(loadPrefs());
    const ctrl = new AbortController();
    fetchVoiceConfig(ctrl.signal)
      .then(setConfig)
      .catch((err: Error) => {
        if (err.name !== "AbortError") setConfig({ enabled: false, reason: err.message, voices: [] });
      });
    return () => ctrl.abort();
  }, []);

  const setPrefs = (patch: Partial<VoicePrefs>) =>
    setPrefsState((prev) => {
      const next = { ...prev, ...patch };
      savePrefs(next);
      return next;
    });

  // Drop a saved voice the server no longer offers.
  const voice =
    prefs.voice && config?.voices.some((v) => v.id === prefs.voice) ? prefs.voice : null;

  return { config, prefs: { ...prefs, voice }, setPrefs };
}
