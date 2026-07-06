import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GrownUpsPage } from "@/components/GrownUpsPage";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    children,
    ...props
  }: { to: string; children?: ReactNode } & Record<string, unknown>) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

import { useQuery } from "@tanstack/react-query";

describe("GrownUpsPage", () => {
  it("renders the stats trio", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        due_today: 5,
        total_reviews: 42,
        current_streak: 3,
        recent: [],
        unseen_milestone: null,
      },
      isLoading: false,
      error: null,
    } as never);

    render(<GrownUpsPage />);

    expect(screen.getByText("For grown-ups")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Due today")).toBeInTheDocument();
    expect(screen.getByText("Total reviews")).toBeInTheDocument();
    expect(screen.getByText("Streak")).toBeInTheDocument();
    expect(screen.getByText("3 days in a row")).toBeInTheDocument();
  });

  it("renders review history with local-timezone timestamps and G8 phrasing", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        due_today: 1,
        total_reviews: 5,
        current_streak: 1,
        recent: [
          { token: "rainbow", interval_days: 0, reviewed_at: "2026-01-01T00:00:00Z" },
          { token: "story", interval_days: 1, reviewed_at: "2026-01-02T00:00:00Z" },
          { token: "family", interval_days: 5, reviewed_at: "2026-01-03T00:00:00Z" },
        ],
        unseen_milestone: null,
      },
      isLoading: false,
      error: null,
    } as never);

    render(<GrownUpsPage />);

    expect(screen.getByRole("heading", { name: "Review history" })).toBeInTheDocument();
    expect(screen.getByText("Back today")).toBeInTheDocument();
    expect(screen.getByText("Back tomorrow")).toBeInTheDocument();
    expect(screen.getByText("Back in 5 days")).toBeInTheDocument();

    const expectedDate = new Date("2026-01-01T00:00:00Z").toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
    expect(screen.getByText(expectedDate)).toBeInTheDocument();
    expect(screen.queryByText(/UTC/)).not.toBeInTheDocument();
  });

  it("renders empty history state", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        due_today: 0,
        total_reviews: 0,
        current_streak: 0,
        recent: [],
        unseen_milestone: null,
      },
      isLoading: false,
      error: null,
    } as never);

    render(<GrownUpsPage />);
    expect(screen.getByText("No reviews yet.")).toBeInTheDocument();
  });

  it("renders the archive link and mic-fix helper text", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        due_today: 0,
        total_reviews: 0,
        current_streak: 0,
        recent: [],
        unseen_milestone: null,
      },
      isLoading: false,
      error: null,
    } as never);

    render(<GrownUpsPage />);

    const link = screen.getByRole("link", { name: "See all words →" });
    expect(link).toHaveAttribute("href", "/archive");
    expect(
      screen.getByText(
        "Microphone is off? Turn it on in your browser settings to check pronunciation.",
      ),
    ).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never);

    render(<GrownUpsPage />);
    expect(screen.queryByText("For grown-ups")).not.toBeInTheDocument();
  });

  it("renders error state with retry", () => {
    const refetch = vi.fn();
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("fail"),
      refetch,
    } as never);

    render(<GrownUpsPage />);
    expect(
      screen.getByText("Couldn't load the stats. Try again."),
    ).toBeInTheDocument();

    const button = screen.getByRole("button", { name: "Try again" });
    fireEvent.click(button);
    expect(refetch).toHaveBeenCalled();
  });
});
