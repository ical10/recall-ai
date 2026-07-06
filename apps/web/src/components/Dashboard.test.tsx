import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Dashboard } from "@/components/Dashboard";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children, ...props }: { children: React.ReactNode }) => (
    <a {...props}>{children}</a>
  ),
}));

vi.mock("@/components/StickerShelf", () => ({
  StickerShelf: () => <section data-testid="sticker-shelf" />,
}));

import { useQuery } from "@tanstack/react-query";

function mockStats(overrides: Record<string, unknown> = {}) {
  vi.mocked(useQuery).mockReturnValue({
    data: {
      due_today: 5,
      total_reviews: 42,
      current_streak: 3,
      recent: [],
      unseen_milestone: null,
      ...overrides,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  } as never);
}

describe("Dashboard", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders My Words heading, start sticker, shelf, and add-word", () => {
    mockStats();

    render(<Dashboard />);

    expect(screen.getByText("My Words")).toBeInTheDocument();
    expect(screen.getByText("Start!")).toBeInTheDocument();
    expect(screen.getByText("5 words ready 🎯")).toBeInTheDocument();
    expect(screen.getByTestId("sticker-shelf")).toBeInTheDocument();
    expect(screen.getByText("Add a new word")).toBeInTheDocument();
  });

  it("renders done state when nothing is due", () => {
    mockStats({ due_today: 0 });

    render(<Dashboard />);

    expect(screen.getByText("All done today! 🎉")).toBeInTheDocument();
    expect(screen.queryByText("Start!")).not.toBeInTheDocument();
  });

  it("renders milestone banner with kid copy when unseen_milestone is set", () => {
    mockStats({ unseen_milestone: 30 });

    render(<Dashboard />);

    expect(screen.getByText("You practiced 30 times! ⭐")).toBeInTheDocument();
    expect(screen.getByText("You are a star!")).toBeInTheDocument();
    expect(screen.getByText("Keep going!")).toBeInTheDocument();
  });

  it("shows loading skeleton while fetching", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<Dashboard />);

    expect(screen.queryByText("My Words")).not.toBeInTheDocument();
  });

  it("shows friendly error card with retry on failure", () => {
    const refetch = vi.fn();
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("fail"),
      refetch,
    } as never);

    render(<Dashboard />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Your words did not load.");
    screen.getByText("Try again").click();
    expect(refetch).toHaveBeenCalled();
  });
});
