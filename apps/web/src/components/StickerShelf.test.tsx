import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StickerShelf } from "@/components/StickerShelf";
import { SEEN_KEYS, hasSeen } from "@/lib/seen";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

import { useQuery } from "@tanstack/react-query";

const items = [
  { id: "1", token: "rainbow", language: "en", part_of_speech: null, definition: "a colorful arc", example_sentence: null },
  { id: "2", token: "happy", language: "en", part_of_speech: null, definition: "feeling good", example_sentence: null },
];

beforeEach(() => {
  localStorage.clear();
});

describe("StickerShelf", () => {
  it("renders the shelf heading", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { items, page: 1, page_size: 60, total: 2 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "My sticker shelf" })).toBeInTheDocument();
  });

  it("flips a sticker to show its definition via click", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { items, page: 1, page_size: 60, total: 2 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    const sticker = screen.getByRole("button", { name: "Show what rainbow means" });
    expect(sticker).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("rainbow")).toBeInTheDocument();

    fireEvent.click(sticker);

    expect(sticker).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("a colorful arc")).toBeInTheDocument();
  });

  it("flips a sticker to show its definition via keyboard", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { items, page: 1, page_size: 60, total: 2 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    const sticker = screen.getByRole("button", { name: "Show what happy means" });
    fireEvent.keyDown(sticker, { key: "Enter", code: "Enter" });

    expect(sticker).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("feeling good")).toBeInTheDocument();
  });

  it("renders the defensive empty state and invokes onEmptyCta when pressed", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { items: [], page: 1, page_size: 60, total: 0 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    const onEmptyCta = vi.fn();
    render(<StickerShelf onEmptyCta={onEmptyCta} />);

    expect(screen.getByText("Your shelf is empty.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Your shelf is empty."));
    expect(onEmptyCta).toHaveBeenCalled();
  });

  it("shows the first-flip hint until dismissed, and sets the seen-key on dismissal", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { items, page: 1, page_size: 60, total: 2 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    expect(screen.getByText("Tap a sticker to see what it means!")).toBeInTheDocument();
    expect(hasSeen(SEEN_KEYS.flip)).toBe(false);

    fireEvent.click(screen.getByLabelText("Dismiss hint"));

    expect(screen.queryByText("Tap a sticker to see what it means!")).not.toBeInTheDocument();
    expect(hasSeen(SEEN_KEYS.flip)).toBe(true);
  });

  it("dismisses the hint on first flip too", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { items, page: 1, page_size: 60, total: 2 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Show what rainbow means" }));

    expect(screen.queryByText("Tap a sticker to see what it means!")).not.toBeInTheDocument();
    expect(hasSeen(SEEN_KEYS.flip)).toBe(true);
  });
});
