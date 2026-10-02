"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Room, RoomEvent } from "livekit-client";
import { toast } from "sonner";
import { createVoiceSession } from "@/lib/voice";

export type DictationState = "idle" | "connecting" | "listening";

export function useDictation(onText: (text: string) => void) {
  const [state, setState] = useState<DictationState>("idle");
  const roomRef = useRef<Room | null>(null);
  const segmentsRef = useRef<Map<string, { text: string; final: boolean }>>(new Map());

  const stop = useCallback(async () => {
    if (!roomRef.current) {
      setState("idle");
      return;
    }
    try {
      await roomRef.current.localParticipant.setMicrophoneEnabled(false);
      await roomRef.current.disconnect();
    } catch (e) {
      console.error("Error stopping dictation:", e);
    } finally {
      roomRef.current = null;
      segmentsRef.current.clear();
      setState("idle");
    }
  }, []);

  const start = useCallback(async () => {
    if (state === "connecting" || state === "listening") return;
    setState("connecting");

    try {
      // Use dummy selection and empty history for dictation
      const sessionInfo = await createVoiceSession({
        selection: null,
        voice: null,
        participantName: "Dictation User",
        history: [],
        mode: "dictation",
      });

      const room = new Room();
      roomRef.current = room;

      // Register transcription handler
      room.registerTextStreamHandler("lk.transcription", (segment) => {
        const { participantInfo, text, final, segmentId } = segment;
        if (participantInfo?.identity !== room.localParticipant.identity) return;

        segmentsRef.current.set(segmentId, { text, final });
        
        // Join segments to get full text so far
        const fullText = Array.from(segmentsRef.current.values())
          .map(s => s.text)
          .join(" ")
          .trim();
        
        onText(fullText);
      });

      await room.connect(sessionInfo.server_url, sessionInfo.participant_token);
      await room.localParticipant.setMicrophoneEnabled(true);
      
      setState("listening");
    } catch (err: any) {
      console.error("Dictation start error:", err);
      if (err?.name === "NotAllowedError" || /permission|denied/i.test(err?.message ?? "")) {
        toast.error("Microphone blocked, please allow it in the browser's site settings");
      } else {
        toast.error(err?.message ?? "Failed to start dictation.");
      }
      setState("idle");
    }
  }, [state, onText]);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return { state, start, stop };
}
