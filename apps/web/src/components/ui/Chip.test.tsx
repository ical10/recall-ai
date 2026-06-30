import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Chip } from "./Chip";

describe("Chip", () => {
  it("renders children", () => {
    render(<Chip>VOCABULARY</Chip>);
    expect(screen.getByText("VOCABULARY")).toBeTruthy();
  });

  it("renders colored dot", () => {
    render(<Chip dotColor="bg-tangerine" data-testid="chip">label</Chip>);
    const dot = screen.getByTestId("chip").querySelector("span");
    expect(dot?.className).toContain("bg-tangerine");
  });

  it("default dot color is honey", () => {
    render(<Chip data-testid="chip">label</Chip>);
    const dot = screen.getByTestId("chip").querySelector("span");
    expect(dot?.className).toContain("bg-honey");
  });
});
