import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StickerShelf } from "@/components/StickerShelf";
import { SEEN_KEYS, hasSeen } from "@/lib/seen";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

import { useQuery } from "@tanstack/react-query";

const items = [
  { id: "1", token: "rainbow", language: "en", part_of_speech: null, definition: "a colorful arc", example_sentence: null, word_audio_url: "/audio/starter/rainbow.mp3" },
  { id: "2", token: "happy", language: "en", part_of_speech: null, definition: "feeling good", example_sentence: null, word_audio_url: null },
];

const playSpy = vi.fn().mockResolvedValue(undefined);

function mockShelf(data: { items: typeof items; total: number }) {
  vi.mocked(useQuery).mockReturnValue({
    data: { page: 1, page_size: 60, ...data },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  } as never);
}

beforeEach(() => {
  localStorage.clear();
  playSpy.mockClear();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(playSpy);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
});

describe("StickerShelf", () => {
  it("renders the shelf heading", () => {
    mockShelf({ items, total: 2 });

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "My sticker shelf" })).toBeInTheDocument();
  });

  it("flips a sticker to show its definition via click", () => {
    mockShelf({ items, total: 2 });

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    const sticker = screen.getByRole("button", { name: "Show what rainbow means" });
    expect(sticker).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("rainbow")).toBeInTheDocument();

    fireEvent.click(sticker);

    expect(sticker).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("a colorful arc")).toBeInTheDocument();
  });

  it("flips a sticker to show its definition via keyboard", () => {
    mockShelf({ items, total: 2 });

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    const sticker = screen.getByRole("button", { name: "Show what happy means" });
    fireEvent.keyDown(sticker, { key: "Enter", code: "Enter" });

    expect(sticker).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("feeling good")).toBeInTheDocument();
  });

  it("renders the defensive empty state and invokes onEmptyCta when pressed", () => {
    mockShelf({ items: [], total: 0 });

    const onEmptyCta = vi.fn();
    render(<StickerShelf onEmptyCta={onEmptyCta} />);

    expect(screen.getByText("Your shelf is empty.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Your shelf is empty."));
    expect(onEmptyCta).toHaveBeenCalled();
  });

  it("shows the first-flip hint until dismissed, and sets the seen-key on dismissal", () => {
    mockShelf({ items, total: 2 });

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    expect(screen.getByText("Tap a sticker to see what it means!")).toBeInTheDocument();
    expect(hasSeen(SEEN_KEYS.flip)).toBe(false);

    fireEvent.click(screen.getByLabelText("Dismiss hint"));

    expect(screen.queryByText("Tap a sticker to see what it means!")).not.toBeInTheDocument();
    expect(hasSeen(SEEN_KEYS.flip)).toBe(true);
  });

  it("plays the word audio when flipping a sticker that has it", () => {
    mockShelf({ items, total: 2 });

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Show what rainbow means" }));
    expect(playSpy).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Show what rainbow means" }));
    expect(playSpy).toHaveBeenCalledOnce();
  });

  it("shows a replay button only when flipped with audio", () => {
    mockShelf({ items, total: 2 });

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Hear rainbow" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show what rainbow means" }));
    fireEvent.click(screen.getByRole("button", { name: "Hear rainbow" }));
    expect(playSpy).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByRole("button", { name: "Show what happy means" }));
    expect(screen.queryByRole("button", { name: "Hear happy" })).not.toBeInTheDocument();
    expect(playSpy).toHaveBeenCalledTimes(2);
  });

  it("dismisses the hint on first flip too", () => {
    mockShelf({ items, total: 2 });

    render(<StickerShelf onEmptyCta={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Show what rainbow means" }));

    expect(screen.queryByText("Tap a sticker to see what it means!")).not.toBeInTheDocument();
    expect(hasSeen(SEEN_KEYS.flip)).toBe(true);
  });
});
