import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceRecorderState =
  | "idle"
  | "recording"
  | "ready"
  | "denied"
  | "unsupported"
  | "error";

const RECORDING_SECONDS = 4;

export function useVoiceRecorder() {
  const [state, setState] = useState<VoiceRecorderState>("idle");
  const [blob, setBlob] = useState<Blob | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(RECORDING_SECONDS);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const countdownRef = useRef<ReturnType<typeof setInterval> | undefined>(
    undefined,
  );

  const clearTimers = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
    timerRef.current = undefined;
    countdownRef.current = undefined;
  }, []);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setState("unsupported");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const chunks: Blob[] = [];
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        clearTimers();
        setBlob(new Blob(chunks, { type: recorder.mimeType }));
        setState("ready");
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      };

      recorder.start();
      setBlob(null);
      setRemainingSeconds(RECORDING_SECONDS);
      setState("recording");
      countdownRef.current = setInterval(() => {
        setRemainingSeconds((seconds) => Math.max(0, seconds - 1));
      }, 1000);
      timerRef.current = setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, RECORDING_SECONDS * 1000);
    } catch (error) {
      clearTimers();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setState(
        typeof error === "object" &&
          error !== null &&
          "name" in error &&
          error.name === "NotAllowedError"
          ? "denied"
          : "error",
      );
    }
  }, [clearTimers]);

  const stop = useCallback(() => {
    clearTimers();
    const recorder = mediaRecorderRef.current;
    if (recorder?.state === "recording") recorder.stop();
  }, [clearTimers]);

  const reset = useCallback(() => {
    clearTimers();
    setState("idle");
    setBlob(null);
    setRemainingSeconds(RECORDING_SECONDS);
  }, [clearTimers]);

  useEffect(
    () => () => {
      clearTimers();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    },
    [clearTimers],
  );

  return {
    state,
    blob,
    supported: state !== "unsupported",
    remainingSeconds,
    start,
    stop,
    reset,
  };
}
