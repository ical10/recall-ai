import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card } from "./Card";
import { Washi } from "./Washi";

describe("Card", () => {
  it("renders children", () => {
    render(<Card data-testid="card">Hello</Card>);
    expect(screen.getByTestId("card")).toHaveTextContent("Hello");
  });

  it("renders default size sm (card-paper)", () => {
    render(<Card data-testid="card">x</Card>);
    expect(screen.getByTestId("card").className).toContain("card-paper");
  });

  it("renders lg size (card-paper--lg)", () => {
    render(<Card size="lg" data-testid="card">x</Card>);
    expect(screen.getByTestId("card").className).toContain("card-paper--lg");
  });

  it("applies tilt class", () => {
    render(<Card tilt="l-2" data-testid="card">x</Card>);
    expect(screen.getByTestId("card").className).toContain("tilt-l-2");
  });

  it("applies animate class", () => {
    render(<Card animate="pop-in" data-testid="card">x</Card>);
    expect(screen.getByTestId("card").className).toContain("animate-pop-in");
  });

  it("renders optional washi", () => {
    render(
      <Card washi={<Washi color="teal" />} data-testid="card">x</Card>
    );
    expect(screen.getByTestId("card").querySelector(".washi--teal")).toBeTruthy();
  });
});
