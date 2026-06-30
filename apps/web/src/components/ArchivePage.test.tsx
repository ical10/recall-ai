import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArchivePage } from "@/components/ArchivePage";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

import { useQuery } from "@tanstack/react-query";

describe("ArchivePage", () => {
  it("renders vocab items", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: {
        items: [
          {
            id: "1",
            token: "serendipity",
            language: "en",
            part_of_speech: "noun",
            definition: "the occurrence of events by chance",
            example_sentence: null,
          },
        ],
        page: 1,
        page_size: 20,
        total: 1,
      },
      isLoading: false,
      error: null,
    } as never);

    render(<ArchivePage />);

    expect(screen.getByText("serendipity")).toBeInTheDocument();
    expect(
      screen.getByText("the occurrence of events by chance"),
    ).toBeInTheDocument();
  });

  it("renders empty state", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { items: [], page: 1, page_size: 20, total: 0 },
      isLoading: false,
      error: null,
    } as never);

    render(<ArchivePage />);
    expect(screen.getByText("No vocabulary items yet.")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never);

    render(<ArchivePage />);
    expect(screen.queryByText("Archive")).not.toBeInTheDocument();
  });

  it("renders error state", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("fail"),
    } as never);

    render(<ArchivePage />);
    expect(screen.getByText("Failed to load archive")).toBeInTheDocument();
  });
});
