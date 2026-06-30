import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RatingButton } from "./RatingButton";

describe("RatingButton", () => {
  it("renders emoji and label", () => {
    render(<RatingButton emoji="😢" label="Again" quality={0} color="berry" data-testid="btn" />);
    const btn = screen.getByTestId("btn");
    expect(btn.textContent).toContain("😢");
    expect(btn.textContent).toContain("Again");
  });

  it("applies btn-pop color variant and flex-col", () => {
    render(<RatingButton emoji="😊" label="Good" quality={4} color="teal" data-testid="btn" />);
    const btn = screen.getByTestId("btn");
    expect(btn.className).toContain("btn-pop--teal");
    expect(btn.className).toContain("flex-col");
  });

  it("fires onClick with quality", () => {
    const fn = vi.fn();
    render(<RatingButton emoji="🔥" label="Easy" quality={5} color="sky" onClick={fn} data-testid="btn" />);
    screen.getByTestId("btn").click();
    expect(fn).toHaveBeenCalledOnce();
  });
});
