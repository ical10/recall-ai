import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FlipSticker } from "@/components/ui/FlipSticker";

beforeEach(() => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
});

describe("FlipSticker", () => {
  it("renders the word face by default", () => {
    render(
      <FlipSticker
        word="rainbow"
        definition="a colorful arc"
        flipped={false}
        tintClass="bg-tangerine-light"
        ariaLabel="Show what rainbow means"
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("rainbow")).toBeInTheDocument();
  });

  it("always renders the definition in the DOM, hidden until flipped", () => {
    render(
      <FlipSticker
        word="rainbow"
        definition="a colorful arc"
        flipped={false}
        tintClass="bg-tangerine-light"
        ariaLabel="Show what rainbow means"
        onToggle={vi.fn()}
      />,
    );

    const definition = screen.getByText("a colorful arc");
    expect(definition).toBeInTheDocument();
    expect(definition.closest("div")).toHaveAttribute("aria-hidden", "true");
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    render(
      <FlipSticker
        word="rainbow"
        definition="a colorful arc"
        flipped={false}
        tintClass="bg-tangerine-light"
        ariaLabel="Show what rainbow means"
        onToggle={onToggle}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Show what rainbow means" }));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("reflects the flipped prop via aria-expanded and swaps aria-hidden on faces", () => {
    render(
      <FlipSticker
        word="rainbow"
        definition="a colorful arc"
        flipped={true}
        tintClass="bg-tangerine-light"
        ariaLabel="Show what rainbow means"
        onToggle={vi.fn()}
      />,
    );

    const sticker = screen.getByRole("button", { name: "Show what rainbow means" });
    expect(sticker).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("rainbow").closest("div")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("a colorful arc").closest("div")).toHaveAttribute(
      "aria-hidden",
      "false",
    );
  });
});
