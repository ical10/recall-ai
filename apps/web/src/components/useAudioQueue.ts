import { useRef, useCallback } from "react";

export function useAudioQueue() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const queueRef = useRef<string[]>([]);

  const play = useCallback((urls: string[]) => {
    const valid = urls.filter((u) => u);
    if (valid.length === 0) return;
    queueRef.current = valid;
    const audio = audioRef.current;
    if (!audio) return;

    audio.src = valid[0];
    audio.play().catch(() => {});

    let idx = 0;
    audio.onended = () => {
      idx++;
      if (idx < valid.length) {
        audio.src = valid[idx];
        audio.play().catch(() => {});
      }
    };
  }, []);

  const stop = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
  }, []);

  return { audioRef, play, stop };
}
