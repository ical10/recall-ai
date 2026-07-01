import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReviewPage } from "@/components/ReviewPage";
import { useReviewSession, type Card } from "@/store/reviewSession";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

vi.mock("@/hooks/useVoiceRecorder", () => ({
  useVoiceRecorder: () => ({
    state: "idle",
    blob: null,
    supported: false,
    start: vi.fn(),
    stop: vi.fn(),
    reset: vi.fn(),
  }),
}));

Object.defineProperty(globalThis, "crypto", {
  value: { randomUUID: () => "00000000-0000-0000-0000-000000000000" },
  writable: true,
});

import { useQuery } from "@tanstack/react-query";

function makeCard(overrides: Partial<Card> = {}): Card {
  return {
    review_id: "r1",
    vocab_item_id: "v1",
    token: "serendipity",
    definition: "the occurrence of events by chance",
    example_sentence: "Finding that book was pure serendipity.",
    ease_factor: 2.5,
    interval_days: 1,
    repetitions: 3,
    due_at: "2026-01-01T00:00:00Z",
    word_audio_url: null,
    example_audio_url: null,
    ...overrides,
  };
}

beforeEach(() => {
  useReviewSession.getState().reset();
});

describe("ReviewPage", () => {
  it("shows loading state while fetching batch", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never);
    render(<ReviewPage />);
    expect(screen.queryByText("serendipity")).not.toBeInTheDocument();
  });

  it("renders the current card token when showing", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard()] },
      isLoading: false,
      error: null,
    } as never);
    render(<ReviewPage />);
    expect(screen.getByText("serendipity")).toBeInTheDocument();
    expect(screen.getByText(/Show Answer/)).toBeInTheDocument();
  });

  it("reveals definition and rating buttons on Show Answer click", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard()] },
      isLoading: false,
      error: null,
    } as never);
    render(<ReviewPage />);
    fireEvent.click(screen.getByText(/Show Answer/));
    fireEvent.click(screen.getByText("Skip"));
    expect(screen.getByText("the occurrence of events by chance")).toBeInTheDocument();
    expect(screen.getByText(/Finding that book was pure serendipity/)).toBeInTheDocument();
    expect(screen.getByText("Good")).toBeInTheDocument();
  });

  it("advances to next card after rating", () => {
    const cards = [
      makeCard({ token: "first" }),
      makeCard({ token: "second", review_id: "r2", vocab_item_id: "v2" }),
    ];
    vi.mocked(useQuery).mockReturnValue({
      data: { cards },
      isLoading: false,
      error: null,
    } as never);
    render(<ReviewPage />);
    expect(screen.getByText("first")).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Show Answer/));
    fireEvent.click(screen.getByText("Skip"));
    fireEvent.click(screen.getByText("Good"));
    expect(screen.getByText("second")).toBeInTheDocument();
    expect(screen.queryByText(/Show Answer/)).toBeInTheDocument();
  });

  it("shows done screen when all cards completed", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard()] },
      isLoading: false,
      error: null,
    } as never);
    render(<ReviewPage />);
    fireEvent.click(screen.getByText(/Show Answer/));
    fireEvent.click(screen.getByText("Skip"));
    fireEvent.click(screen.getByText("Good"));
    expect(screen.getByText(/All caught up/)).toBeInTheDocument();
    expect(screen.getByText(/Back to deck/)).toBeInTheDocument();
  });

  it("shows empty message when no cards due", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [] },
      isLoading: false,
      error: null,
    } as never);
    render(<ReviewPage />);
    expect(screen.getByText(/No cards due/)).toBeInTheDocument();
  });

  it("reveals on Space keypress", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard()] },
      isLoading: false,
      error: null,
    } as never);
    render(<ReviewPage />);
    fireEvent.keyDown(window, { key: " " });
    expect(screen.getByText("the occurrence of events by chance")).toBeInTheDocument();
  });
});
