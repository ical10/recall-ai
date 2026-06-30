import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Eyebrow } from "./Eyebrow";

describe("Eyebrow", () => {
  it("renders children", () => {
    render(<Eyebrow>DAILY REVIEW</Eyebrow>);
    expect(screen.getByText("DAILY REVIEW")).toBeTruthy();
  });

  it("has mono font and uppercase styling", () => {
    render(<Eyebrow data-testid="eb">label</Eyebrow>);
    const el = screen.getByTestId("eb");
    expect(el.className).toContain("font-mono");
    expect(el.className).toContain("uppercase");
  });

  it("accepts className", () => {
    render(<Eyebrow className="text-xs" data-testid="eb">label</Eyebrow>);
    expect(screen.getByTestId("eb").className).toContain("text-xs");
  });
});
