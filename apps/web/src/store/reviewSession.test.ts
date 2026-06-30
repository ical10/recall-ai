import { describe, it, expect } from "vitest";
import { useReviewSession, type Card } from "@/store/reviewSession";

function makeCard(overrides: Partial<Card> = {}): Card {
  return {
    review_id: "r1",
    vocab_item_id: "v1",
    token: "test",
    definition: "a test",
    example_sentence: null,
    ease_factor: 2.5,
    interval_days: 1,
    repetitions: 0,
    due_at: "2026-01-01T00:00:00Z",
    word_audio_url: null,
    example_audio_url: null,
    ...overrides,
  };
}

describe("reviewSession store", () => {
  it("starts in idle phase with empty cards", () => {
    const store = useReviewSession.getState();
    expect(store.phase).toBe("idle");
    expect(store.cards).toEqual([]);
    expect(store.activeIndex).toBe(0);
  });

  it("loadCards transitions idle → showing", () => {
    const cards = [makeCard({ token: "hello" }), makeCard({ token: "world" })];
    useReviewSession.getState().loadCards(cards);

    const state = useReviewSession.getState();
    expect(state.phase).toBe("showing");
    expect(state.cards).toHaveLength(2);
    expect(state.activeIndex).toBe(0);
  });

  it("reveal transitions showing → revealed", () => {
    useReviewSession.getState().loadCards([makeCard()]);
    useReviewSession.getState().reveal();

    expect(useReviewSession.getState().phase).toBe("revealed");
  });

  it("next transitions revealed → showing (next card)", () => {
    const cards = [makeCard({ token: "a" }), makeCard({ token: "b" })];
    useReviewSession.getState().loadCards(cards);
    useReviewSession.getState().reveal();
    useReviewSession.getState().nextCard();

    const state = useReviewSession.getState();
    expect(state.phase).toBe("showing");
    expect(state.activeIndex).toBe(1);
  });

  it("next on last card transitions revealed → idle and sets completed", () => {
    useReviewSession.getState().loadCards([makeCard()]);
    useReviewSession.getState().reveal();
    useReviewSession.getState().nextCard();

    const state = useReviewSession.getState();
    expect(state.phase).toBe("idle");
    expect(state.cards).toEqual([]);
    expect(state.completed).toBe(true);
  });

  it("completed is false on fresh loadCards", () => {
    useReviewSession.getState().loadCards([makeCard()]);
    expect(useReviewSession.getState().completed).toBe(false);
  });

  it("reveal from idle is rejected (illegal transition)", () => {
    useReviewSession.setState({ cards: [], phase: "idle" });
    expect(() => useReviewSession.getState().reveal()).toThrow(
      "Cannot reveal from idle",
    );
  });

  it("next from showing is rejected (must reveal first)", () => {
    useReviewSession.getState().loadCards([makeCard()]);
    expect(() => useReviewSession.getState().nextCard()).toThrow(
      "Cannot advance from showing",
    );
  });

  it("reset returns to idle", () => {
    useReviewSession.getState().loadCards([makeCard()]);
    useReviewSession.getState().reset();

    const state = useReviewSession.getState();
    expect(state.phase).toBe("idle");
    expect(state.cards).toEqual([]);
    expect(state.activeIndex).toBe(0);
  });
});
