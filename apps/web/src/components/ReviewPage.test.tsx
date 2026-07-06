import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewPage } from "@/components/ReviewPage";
import { useReviewSession, type Card } from "@/store/reviewSession";

vi.mock("@tanstack/react-query", () => ({ useQuery: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, ...props }: React.PropsWithChildren<{ to: string }>) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));
vi.mock("@/hooks/useVoiceRecorder", () => ({
  useVoiceRecorder: () => ({
    state: "idle",
    blob: null,
    remainingSeconds: 4,
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

function mockBatch(cards: Card[]) {
  vi.mocked(useQuery).mockReturnValue({
    data: { cards },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  } as never);
}

beforeEach(() => {
  localStorage.clear();
  useReviewSession.setState({ outbox: [], flushing: false });
  useReviewSession.getState().reset();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ applied: 1, skipped: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
});

describe("ReviewPage", () => {
  it("makes the prompt card the reveal button", () => {
    mockBatch([makeCard()]);
    render(<ReviewPage />);

    expect(screen.getByRole("button", { name: "Show the meaning" })).toHaveTextContent(
      "Tap to see!",
    );
    expect(screen.queryByText("Show Answer")).not.toBeInTheDocument();
  });

  it("gates a card without reference audio and hides the replay button", async () => {
    mockBatch([makeCard()]);
    render(<ReviewPage />);
    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));

    expect(
      await screen.findByRole("button", { name: "🎤 Say the word!" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "😊 Got it!" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Hear it again" })).not.toBeInTheDocument();
  });

  it("gates every card before showing its rating row", async () => {
    mockBatch([
      makeCard({ token: "first", word_audio_url: "/first.mp3" }),
      makeCard({
        token: "second",
        review_id: "r2",
        vocab_item_id: "v2",
        word_audio_url: "/second.mp3",
      }),
    ]);
    render(<ReviewPage />);

    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));
    expect(screen.queryByRole("button", { name: "😊 Got it!" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    fireEvent.click(screen.getByRole("button", { name: "😊 Got it!" }));

    expect(screen.getByText("second")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show the meaning" }));
    expect(screen.getByRole("button", { name: "Skip" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "😊 Got it!" })).not.toBeInTheDocument();
  });

  it("reveals with the Space key", () => {
    mockBatch([makeCard()]);
    render(<ReviewPage />);
    fireEvent.keyDown(window, { key: " " });
    expect(screen.getByText("the occurrence of events by chance")).toBeInTheDocument();
  });

  it("shows the zero-due escape", () => {
    mockBatch([]);
    render(<ReviewPage />);
    expect(screen.getByText("No words today!")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add a new word" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("shows the friendly load error and retries", async () => {
    const refetch = vi.fn();
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("offline"),
      refetch,
    } as never);
    render(<ReviewPage />);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(refetch).toHaveBeenCalledOnce());
    expect(screen.getByRole("alert")).toHaveTextContent("Your words did not load.");
  });
});
