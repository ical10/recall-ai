export const SEEN_KEYS = {
  startWiggle: "recall.hint.start-wiggle",
  flip: "recall.hint.flip",
  rating: "recall.hint.rating",
  mic: "recall.hint.mic",
  micDenied: "recall.mic.denied",
  firstDone: "recall.seen.first-done",
} as const;

export type SeenKey = (typeof SEEN_KEYS)[keyof typeof SEEN_KEYS];

export function hasSeen(key: SeenKey): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return true;
  }
}

export function markSeen(key: SeenKey): void {
  try {
    localStorage.setItem(key, "1");
  } catch {
    // ponytail: storage unavailable (private mode) — hints simply reappear
  }
}

export function seenOnce(key: SeenKey): boolean {
  if (hasSeen(key)) return false;
  markSeen(key);
  return true;
}
