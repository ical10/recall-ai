import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IconBadge } from "./IconBadge";
import { Icon } from "./Icon";

describe("IconBadge", () => {
  it("renders an icon inside a rounded box", () => {
    render(
      <IconBadge color="bg-teal" data-testid="badge">
        <Icon name="check" className="h-4 w-4 text-cream-50" />
      </IconBadge>,
    );
    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("border-2");
    expect(badge.className).toContain("border-ink");
    expect(badge.className).toContain("bg-teal");
    expect(badge.querySelector("svg")).toBeTruthy();
  });

  it("applies size variant sm", () => {
    render(<IconBadge size="sm" data-testid="badge"><span /></IconBadge>);
    expect(screen.getByTestId("badge").className).toContain("rounded-lg");
  });

  it("applies size variant md (default)", () => {
    render(<IconBadge data-testid="badge"><span /></IconBadge>);
    expect(screen.getByTestId("badge").className).toContain("rounded-2xl");
  });

  it("applies size variant lg", () => {
    render(<IconBadge size="lg" data-testid="badge"><span /></IconBadge>);
    expect(screen.getByTestId("badge").className).toContain("rounded-3xl");
  });

  it("applies shadow on lg size", () => {
    render(<IconBadge size="lg" data-testid="badge"><span /></IconBadge>);
    expect(screen.getByTestId("badge").className).toContain("shadow-pop");
  });
});
