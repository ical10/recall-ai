import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SettingsPage } from "@/components/SettingsPage";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(() => ({ isPending: false, isError: false, mutate: vi.fn() })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

import { useQuery } from "@tanstack/react-query";

describe("SettingsPage", () => {
  it("renders all tags from API", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        interest_tags: ["food"],
        all_tags: ["animals", "colors", "food", "school"],
      },
      isLoading: false,
      error: null,
    } as never);

    render(<SettingsPage />);

    expect(screen.getByText("food")).toBeInTheDocument();
    expect(screen.getByText("animals")).toBeInTheDocument();
    expect(screen.getByText("colors")).toBeInTheDocument();
    expect(screen.getByText("school")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never);

    render(<SettingsPage />);
    expect(screen.queryByText("Interest Tags")).not.toBeInTheDocument();
  });

  it("renders error state", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("fail"),
    } as never);

    render(<SettingsPage />);
    expect(screen.getByText("Failed to load settings")).toBeInTheDocument();
  });
});
