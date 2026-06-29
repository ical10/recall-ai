import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Dashboard } from "@/components/Dashboard";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

import { useQuery } from "@tanstack/react-query";

describe("Dashboard", () => {
  it("renders due_today, total_reviews, and streak", () => {
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

    render(<Dashboard />);

    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
    expect(screen.getByText("Due Today")).toBeInTheDocument();
    expect(screen.getByText("Total Reviews")).toBeInTheDocument();
    expect(screen.getByText("Streak")).toBeInTheDocument();
  });

  it("renders milestone banner when unseen_milestone is set", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        due_today: 0,
        total_reviews: 30,
        current_streak: 1,
        recent: [],
        unseen_milestone: 30,
      },
      isLoading: false,
      error: null,
    } as never);

    render(<Dashboard />);

    expect(screen.getByText(/30 reviews/)).toBeInTheDocument();
  });

  it("renders recent review tokens", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        due_today: 1,
        total_reviews: 5,
        current_streak: 1,
        recent: [
          { token: "ephemeral", interval_days: 1, reviewed_at: "2026-01-01T00:00:00Z" },
          { token: "serendipity", interval_days: 7, reviewed_at: "2026-01-02T00:00:00Z" },
        ],
        unseen_milestone: null,
      },
      isLoading: false,
      error: null,
    } as never);

    render(<Dashboard />);

    expect(screen.getByText("ephemeral")).toBeInTheDocument();
    expect(screen.getByText("serendipity")).toBeInTheDocument();
  });

  it("shows loading skeleton while fetching", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never);

    render(<Dashboard />);

    expect(screen.queryByText("Due Today")).not.toBeInTheDocument();
  });

  it("shows error message on failure", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("fail"),
    } as never);

    render(<Dashboard />);

    expect(screen.getByText("Failed to load dashboard")).toBeInTheDocument();
  });
});
