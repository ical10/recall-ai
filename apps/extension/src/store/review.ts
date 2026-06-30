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

type Phase = "idle" | "showing" | "revealed" | "done";

interface ReviewState {
  phase: Phase;
  cards: Card[];
  activeIndex: number;
  loadCards: (cards: Card[]) => void;
  reveal: () => void;
  nextCard: () => void;
  reset: () => void;
}

export const useReviewSession = create<ReviewState>((set, get) => ({
  phase: "idle",
  cards: [],
  activeIndex: 0,

  loadCards: (cards) => {
    set({ cards, activeIndex: 0, phase: "showing" });
  },

  reveal: () => {
    if (get().phase !== "showing") return;
    set({ phase: "revealed" });
  },

  nextCard: () => {
    const { activeIndex, cards } = get();
    const nextIndex = activeIndex + 1;
    if (nextIndex >= cards.length) {
      set({ phase: "done", cards: [], activeIndex: 0 });
    } else {
      set({ activeIndex: nextIndex, phase: "showing" });
    }
  },

  reset: () => {
    set({ phase: "idle", cards: [], activeIndex: 0 });
  },
}));
