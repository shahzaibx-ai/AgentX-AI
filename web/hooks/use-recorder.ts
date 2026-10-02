"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { toast } from "sonner";

export function useRecorder() {
  const [state, setState] = useState<"idle" | "recording" | "transcribing">("idle");
  const [levels, setLevels] = useState<number[]>([]);
  const [seconds, setSeconds] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationRef = useRef<number | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const cleanup = useCallback(() => {
    if (mediaRecorderRef.current?.state !== "inactive") {
      mediaRecorderRef.current?.stop();
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (animationRef.current) cancelAnimationFrame(animationRef.current);
    if (timerRef.current) clearInterval(timerRef.current);
    analyserRef.current = null;
    chunksRef.current = [];
    setLevels((prev) => (prev.length ? [] : prev));
    setSeconds((prev) => (prev ? 0 : prev));
  }, []);

  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      // Waveform logic
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtx();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);

      audioContextRef.current = ctx;
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateLevels = () => {
        analyser.getByteFrequencyData(dataArray);
        // Simple RMS approximation
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i] * dataArray[i];
        const rms = Math.sqrt(sum / dataArray.length) / 128;

        setLevels((prev) => [...prev.slice(-47), rms]);
        animationRef.current = requestAnimationFrame(updateLevels);
      };
      updateLevels();

      timerRef.current = setInterval(() => {
        setSeconds((s) => s + 1);
      }, 1000);

      recorder.start();
      setState("recording");

      // Auto-stop at 120s
      setTimeout(() => {
        // Use a ref or current state logic inside the timeout
        if (mediaRecorderRef.current?.state === "recording") stop();
      }, 120000);

    } catch (err: any) {
      const msg = err.name === "NotAllowedError" ? "Microphone blocked" :
                  err.name === "NotFoundError" ? "No microphone found" :
                  err.name === "NotReadableError" ? "Microphone not readable" : "Mic error";
      toast.error(msg);
      cleanup();
      setState("idle");
    }
  }, [cleanup]);

  const stop = useCallback(async () => {
    if (state !== "recording") return "";

    setState("transcribing");

    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      await new Promise<void>((res) => {
        const rec = mediaRecorderRef.current;
        if (rec) {
          rec.onstop = () => { res(); };
        } else {
          res();
        }
      });
    }

    const blob = new Blob(chunksRef.current, { type: mediaRecorderRef.current?.mimeType || "audio/webm" });

    try {
      const formData = new FormData();
      formData.append("file", blob, "recording.webm");

      const res = await fetch("/api/stt", { method: "POST", body: formData });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `API error ${res.status}`);
      }
      const data = await res.json();

      cleanup();
      setState("idle");
      return data.text || "";
    } catch (err: any) {
      toast.error(err.message || "Transcription failed");
      cleanup();
      setState("idle");
      return "";
    }
  }, [state, cleanup]);

  const cancel = useCallback(() => {
    cleanup();
    setState("idle");
  }, [cleanup]);

  return useMemo(() => ({
    state,
    levels,
    seconds,
    start,
    stop,
    cancel,
  }), [state, levels, seconds, start, stop, cancel]);
}
