import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Washi } from "./Washi";

describe("Washi", () => {
  it("renders a decorative element", () => {
    render(<Washi data-testid="tape" />);
    const el = screen.getByTestId("tape");
    expect(el.className).toContain("washi");
  });

  it("default color is honey", () => {
    render(<Washi data-testid="tape" />);
    expect(screen.getByTestId("tape").className).not.toContain("washi--teal");
  });

  it("applies teal color variant", () => {
    render(<Washi color="teal" data-testid="tape" />);
    expect(screen.getByTestId("tape").className).toContain("washi--teal");
  });

  it("accepts position className", () => {
    render(<Washi className="-top-3 -left-3" data-testid="tape" />);
    expect(screen.getByTestId("tape").className).toContain("-top-3");
  });
});
