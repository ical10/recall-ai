import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders as button by default", () => {
    render(<Button>Click</Button>);
    expect(screen.getByRole("button")).toHaveTextContent("Click");
  });

  it("renders default primary variant", () => {
    render(<Button data-testid="btn">Click</Button>);
    expect(screen.getByTestId("btn").className).toContain("btn-pop--primary");
  });

  it("applies variant classes", () => {
    const variants = ["primary", "ink", "teal", "berry", "honey", "sky", "ghost"] as const;
    for (const v of variants) {
      const { unmount } = render(<Button variant={v} data-testid="btn">x</Button>);
      expect(screen.getByTestId("btn").className).toContain(`btn-pop--${v}`);
      unmount();
    }
  });

  it("applies fullWidth class", () => {
    render(<Button fullWidth data-testid="btn">x</Button>);
    expect(screen.getByTestId("btn").className).toContain("w-full");
  });

  it("renders trailing glyph", () => {
    render(<Button glyph="→">Next</Button>);
    expect(screen.getByText("→")).toBeTruthy();
  });

  it("renders as anchor when as='a'", () => {
    render(<Button as="a" href="/go" data-testid="btn">Link</Button>);
    const el = screen.getByTestId("btn");
    expect(el.tagName).toBe("A");
    expect(el.getAttribute("href")).toBe("/go");
  });

  it("fires onClick", () => {
    const fn = vi.fn();
    render(<Button onClick={fn}>Fire</Button>);
    screen.getByText("Fire").click();
    expect(fn).toHaveBeenCalledOnce();
  });

  it("accepts className", () => {
    render(<Button className="extra" data-testid="btn">x</Button>);
    expect(screen.getByTestId("btn").className).toContain("extra");
  });
});
