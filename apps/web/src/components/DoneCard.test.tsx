import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DoneCard } from "@/components/DoneCard";
import { SEEN_KEYS } from "@/lib/seen";
import { useReviewSession } from "@/store/reviewSession";

const realFlushRatings = useReviewSession.getState().flushRatings;

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, ...props }: React.PropsWithChildren<{ to: string }>) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

beforeEach(() => {
  localStorage.clear();
  useReviewSession.setState({
    outbox: [],
    flushing: false,
    flushRatings: realFlushRatings,
  });
});

describe("DoneCard", () => {
  it("shows the first-ever message and twelve confetti dots", () => {
    const { container } = render(<DoneCard count={3} />);
    expect(screen.getByText("You learned your first words!")).toBeInTheDocument();
    expect(container.querySelectorAll(".confetti-dot")).toHaveLength(12);
  });

  it("shows the regular message with the real count", () => {
    localStorage.setItem(SEEN_KEYS.firstDone, "1");
    const { container } = render(<DoneCard count={7} />);
    expect(screen.getByText("7 words done today! 🎉")).toBeInTheDocument();
    expect(container.querySelectorAll(".confetti-dot")).toHaveLength(8);
    expect(screen.getByRole("link", { name: "Go to My Words" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("flushes remaining ratings and shows Saving", () => {
    const flushRatings = vi.fn().mockResolvedValue(undefined);
    useReviewSession.setState({
      outbox: [
        {
          rating_id: "rating-1",
          card_id: "card-1",
          grade: 4,
          rated_at: "2026-07-06T00:00:00Z",
        },
      ],
      flushRatings,
    });

    render(<DoneCard count={1} />);
    expect(screen.getByText("Saving…")).toBeInTheDocument();
    expect(flushRatings).toHaveBeenCalledOnce();
  });
});
