import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FlipSticker } from "@/components/ui/FlipSticker";

function renderSticker(overrides: Partial<React.ComponentProps<typeof FlipSticker>> = {}) {
  return render(
    <FlipSticker
      word="rainbow"
      definition="a colorful arc"
      flipped={false}
      tintClass="bg-tangerine-light"
      ariaLabel="Show what rainbow means"
      onToggle={vi.fn()}
      {...overrides}
    />,
  );
}

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
    renderSticker();

    expect(screen.getByText("rainbow")).toBeInTheDocument();
  });

  it("always renders the definition in the DOM, hidden until flipped", () => {
    renderSticker();

    const definition = screen.getByText("a colorful arc");
    expect(definition).toBeInTheDocument();
    expect(definition.closest("div")).toHaveAttribute("aria-hidden", "true");
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    renderSticker({ onToggle });

    fireEvent.click(screen.getByRole("button", { name: "Show what rainbow means" }));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("reflects the flipped prop via aria-expanded and swaps aria-hidden on faces", () => {
    renderSticker({ flipped: true });

    const sticker = screen.getByRole("button", { name: "Show what rainbow means" });
    expect(sticker).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("rainbow").closest("div")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("a colorful arc").closest("div")).toHaveAttribute(
      "aria-hidden",
      "false",
    );
  });
});
