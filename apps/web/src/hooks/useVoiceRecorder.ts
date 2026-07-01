import { useState, useRef, useCallback, useEffect } from "react";

export function useVoiceRecorder() {
  const [state, setState] = useState<
    "idle" | "recording" | "ready" | "error"
  >("idle");
  const [blob, setBlob] = useState<Blob | null>(null);
  const [supported, setSupported] = useState(true);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setSupported(false);
      setState("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType });
        setBlob(audioBlob);
        setState("ready");
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      setState("recording");
      setBlob(null);

      timerRef.current = setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, 4000);
    } catch {
      setSupported(false);
      setState("error");
    }
  }, []);

  const stop = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === "recording") {
      recorder.stop();
    }
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const reset = useCallback(() => {
    setState("idle");
    setBlob(null);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return {
    state,
    blob,
    supported,
    start,
    stop,
    reset,
  };
}
