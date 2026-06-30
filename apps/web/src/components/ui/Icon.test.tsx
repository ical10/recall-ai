import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Icon } from "./Icon";

describe("Icon", () => {
  it("renders check icon", () => {
    render(<Icon name="check" data-testid="icon" />);
    const svg = screen.getByTestId("icon");
    expect(svg.tagName).toBe("svg");
    expect(svg.querySelector("path")?.getAttribute("d")).toBe("M5 12l5 5L20 7");
  });

  it("renders clock icon", () => {
    render(<Icon name="clock" data-testid="icon" />);
    const svg = screen.getByTestId("icon");
    expect(svg.querySelector("circle")).toBeTruthy();
  });

  it("renders flame icon with fill currentColor", () => {
    render(<Icon name="flame" data-testid="icon" />);
    const svg = screen.getByTestId("icon");
    expect(svg.querySelector("path")?.getAttribute("fill")).toBe("currentColor");
  });

  it("renders info icon", () => {
    render(<Icon name="info" data-testid="icon" />);
    const svg = screen.getByTestId("icon");
    expect(svg.querySelector("circle")).toBeTruthy();
  });

  it("renders google icon with brand colors", () => {
    render(<Icon name="google" data-testid="icon" />);
    const svg = screen.getByTestId("icon");
    const paths = svg.querySelectorAll("path");
    expect(paths[0]?.getAttribute("fill")).toBe("#4285F4");
  });

  it("passes className to svg", () => {
    render(<Icon name="check" className="h-6 w-6 text-teal" data-testid="icon" />);
    const svg = screen.getByTestId("icon");
    const cls = svg.getAttribute("class") ?? "";
    expect(cls).toContain("h-6");
    expect(cls).toContain("w-6");
    expect(cls).toContain("text-teal");
  });

  it("default viewBox is 0 0 24 24", () => {
    render(<Icon name="flame" data-testid="icon" />);
    expect(screen.getByTestId("icon").getAttribute("viewBox")).toBe("0 0 24 24");
  });
});
