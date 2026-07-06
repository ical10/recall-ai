import { fetchApi } from "@/api/client";
import { create } from "zustand";

export interface Card {
  review_id: string;
  vocab_item_id: string;
  token: string;
  definition: string;
  example_sentence: string | null;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
  due_at: string;
  word_audio_url: string | null;
  example_audio_url: string | null;
}

export interface QueuedRating {
  rating_id: string;
  card_id: string;
  grade: number;
  rated_at: string;
}

type Phase = "idle" | "showing" | "gated" | "ratable";

interface ReviewSessionState {
  phase: Phase;
  cards: Card[];
  activeIndex: number;
  sessionCount: number;
  completed: boolean;
  outbox: QueuedRating[];
  flushing: boolean;
  loadCards: (cards: Card[]) => void;
  reveal: () => void;
  allowRating: () => void;
  nextCard: () => void;
  enqueueRating: (rating: QueuedRating) => void;
  flushRatings: () => Promise<void>;
  reset: () => void;
}

const OUTBOX_KEY = "recall.review.rating-outbox";
const INITIAL_RETRY_MS = 250;
const MAX_RETRY_MS = 4000;
let retryDelay = INITIAL_RETRY_MS;
let retryTimer: ReturnType<typeof setTimeout> | undefined;

function readOutbox(): QueuedRating[] {
  try {
    const value = localStorage.getItem(OUTBOX_KEY);
    if (!value) return [];
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (rating): rating is QueuedRating =>
        typeof rating === "object" &&
        rating !== null &&
        typeof rating.rating_id === "string" &&
        typeof rating.card_id === "string" &&
        typeof rating.grade === "number" &&
        typeof rating.rated_at === "string",
    );
  } catch {
    return [];
  }
}

function persistOutbox(outbox: QueuedRating[]) {
  try {
    localStorage.setItem(OUTBOX_KEY, JSON.stringify(outbox));
  } catch {
    return;
  }
}

export const useReviewSession = create<ReviewSessionState>((set, get) => ({
  phase: "idle",
  cards: [],
  activeIndex: 0,
  sessionCount: 0,
  completed: false,
  outbox: readOutbox(),
  flushing: false,

  loadCards: (cards) => {
    // A background refetch of the batch query (e.g. tab focus mid-session)
    // must not reset progress already in flight — only apply a fresh batch
    // when no session is active.
    if (get().phase !== "idle") return;
    set({
      cards,
      activeIndex: 0,
      sessionCount: cards.length,
      phase: cards.length > 0 ? "showing" : "idle",
      completed: false,
    });
  },

  reveal: () => {
    const { phase } = get();
    if (phase !== "showing") throw new Error(`Cannot reveal from ${phase}`);
    set({ phase: "gated" });
  },

  allowRating: () => {
    const { phase } = get();
    if (phase !== "gated") return;
    set({ phase: "ratable" });
  },

  nextCard: () => {
    const { phase, activeIndex, cards } = get();
    if (phase !== "ratable") throw new Error(`Cannot advance from ${phase}`);
    const nextIndex = activeIndex + 1;
    if (nextIndex >= cards.length) {
      set({ phase: "idle", cards: [], activeIndex: 0, completed: true });
    } else {
      set({ activeIndex: nextIndex, phase: "showing" });
    }
  },

  enqueueRating: (rating) => {
    const outbox = [...get().outbox, rating];
    persistOutbox(outbox);
    set({ outbox });
    void get().flushRatings();
  },

  flushRatings: async () => {
    if (get().flushing || get().outbox.length === 0) return;
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = undefined;
    }

    const batch = get().outbox;
    const sentIds = new Set(batch.map((rating) => rating.rating_id));
    set({ flushing: true });
    try {
      await fetchApi("/api/review/ratings", {
        method: "POST",
        body: JSON.stringify({ ratings: batch }),
      });
      const outbox = get().outbox.filter(
        (rating) => !sentIds.has(rating.rating_id),
      );
      persistOutbox(outbox);
      retryDelay = INITIAL_RETRY_MS;
      set({ outbox, flushing: false });
      if (outbox.length > 0) void get().flushRatings();
    } catch {
      set({ flushing: false });
      retryTimer = setTimeout(() => {
        retryTimer = undefined;
        void get().flushRatings();
      }, retryDelay);
      retryDelay = Math.min(retryDelay * 2, MAX_RETRY_MS);
    }
  },

  reset: () => {
    set({
      phase: "idle",
      cards: [],
      activeIndex: 0,
      sessionCount: 0,
      completed: false,
    });
  },
}));
