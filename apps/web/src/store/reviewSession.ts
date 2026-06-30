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

type Phase = "idle" | "showing" | "revealed";

interface ReviewSessionState {
  phase: Phase;
  cards: Card[];
  activeIndex: number;
  completed: boolean;
  loadCards: (cards: Card[]) => void;
  reveal: () => void;
  nextCard: () => void;
  reset: () => void;
}

export const useReviewSession = create<ReviewSessionState>((set, get) => ({
  phase: "idle",
  cards: [],
  activeIndex: 0,
  completed: false,

  loadCards: (cards) => {
    set({ cards, activeIndex: 0, phase: "showing", completed: false });
  },

  reveal: () => {
    const { phase } = get();
    if (phase !== "showing") {
      throw new Error(`Cannot reveal from ${phase}`);
    }
    set({ phase: "revealed" });
  },

  nextCard: () => {
    const { phase, activeIndex, cards } = get();
    if (phase !== "revealed") {
      throw new Error(`Cannot advance from ${phase}`);
    }
    const nextIndex = activeIndex + 1;
    if (nextIndex >= cards.length) {
      set({ phase: "idle", cards: [], activeIndex: 0, completed: true });
    } else {
      set({ activeIndex: nextIndex, phase: "showing" });
    }
  },

  reset: () => {
    set({ phase: "idle", cards: [], activeIndex: 0, completed: false });
  },
}));
