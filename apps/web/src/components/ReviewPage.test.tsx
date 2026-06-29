import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReviewPage } from "@/components/ReviewPage";
import { useReviewSession, type Card } from "@/store/reviewSession";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

import { useQuery, useMutation } from "@tanstack/react-query";

// Default: mutate() succeeds and invokes the component's onSuccess (which advances).
function mockMutationSuccess() {
  vi.mocked(useMutation).mockImplementation(
    ((opts: { onSuccess?: (...args: unknown[]) => void }) => ({
      mutate: (vars: unknown) =>
        opts.onSuccess?.({ applied: 1, skipped: 0 }, vars, undefined, undefined),
      isPending: false,
      isError: false,
    })) as unknown as typeof useMutation,
  );
}

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
  mockMutationSuccess();
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

  it("renders the current card token and interval when showing", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard()] },
      isLoading: false,
      error: null,
    } as never);

    render(<ReviewPage />);
    expect(screen.getByText("serendipity")).toBeInTheDocument();
    expect(screen.getByText(/Show Answer/)).toBeInTheDocument();
  });

  it("reveals definition and rating buttons on Show Answer click", async () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard()] },
      isLoading: false,
      error: null,
    } as never);

    render(<ReviewPage />);
    fireEvent.click(screen.getByText(/Show Answer/));

    expect(screen.getByText("the occurrence of events by chance")).toBeInTheDocument();
    expect(screen.getByText(/Finding that book was pure serendipity/)).toBeInTheDocument();
    for (const label of ["Again", "Hard", "Good", "Easy"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("advances to next card after a rating persists", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "Good" }));

    expect(screen.getByText("second")).toBeInTheDocument();
    expect(screen.queryByText(/Show Answer/)).toBeInTheDocument();
  });

  it("shows the daily-done message when all cards are rated", async () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard()] },
      isLoading: false,
      error: null,
    } as never);

    render(<ReviewPage />);
    fireEvent.click(screen.getByText(/Show Answer/));
    fireEvent.click(screen.getByRole("button", { name: "Good" }));

    expect(screen.getByText(/No more cards to review today/)).toBeInTheDocument();
  });

  it("surfaces an error and stays on the card when the rating fails", async () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [makeCard({ token: "first" })] },
      isLoading: false,
      error: null,
    } as never);
    // Rating fails: mutate does not call onSuccess, and isError is true.
    vi.mocked(useMutation).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
    } as never);

    render(<ReviewPage />);
    fireEvent.click(screen.getByText(/Show Answer/));
    fireEvent.click(screen.getByRole("button", { name: "Good" }));

    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText(/Couldn't save your rating/)).toBeInTheDocument();
    expect(screen.queryByText(/No more cards to review today/)).not.toBeInTheDocument();
  });

  it("shows the daily-done message when the batch is empty", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { cards: [] },
      isLoading: false,
      error: null,
    } as never);

    render(<ReviewPage />);
    expect(screen.getByText(/No more cards to review today/)).toBeInTheDocument();
  });
});
