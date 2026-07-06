import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
    word_audio_url: "word.mp3",
    example_audio_url: null,
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
  useReviewSession.setState({ outbox: [], flushing: false });
  useReviewSession.getState().reset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("reviewSession store", () => {
  it("gates every revealed card before it can be rated", () => {
    useReviewSession.getState().loadCards([
      makeCard(),
      makeCard({ review_id: "r2", token: "next" }),
    ]);

    useReviewSession.getState().reveal();
    expect(useReviewSession.getState().phase).toBe("gated");
    useReviewSession.getState().allowRating();
    useReviewSession.getState().nextCard();
    expect(useReviewSession.getState().phase).toBe("showing");
    useReviewSession.getState().reveal();
    expect(useReviewSession.getState().phase).toBe("gated");
  });

  it("retries the same queued rating id after failure", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ applied: 1, skipped: 0 })));
    vi.stubGlobal("fetch", fetchMock);
    const rating = {
      rating_id: "rating-1",
      card_id: "r1",
      grade: 4,
      rated_at: "2026-07-06T00:00:00Z",
    };

    useReviewSession.getState().enqueueRating(rating);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(useReviewSession.getState().outbox).toEqual([rating]);

    await vi.advanceTimersByTimeAsync(250);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const firstBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    const retryBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(firstBody.ratings[0].rating_id).toBe("rating-1");
    expect(retryBody.ratings[0].rating_id).toBe("rating-1");
    expect(useReviewSession.getState().outbox).toEqual([]);
  });
});
