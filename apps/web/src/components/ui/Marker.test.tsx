import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Marker } from "./Marker";

describe("Marker", () => {
  it("renders children", () => {
    render(<Marker>highlighted</Marker>);
    expect(screen.getByText("highlighted")).toBeTruthy();
  });

  it("default color is honey", () => {
    render(<Marker data-testid="m">text</Marker>);
    expect(screen.getByTestId("m").className).toContain("marker");
    expect(screen.getByTestId("m").className).not.toContain("marker--teal");
  });

  it("applies teal color variant", () => {
    render(<Marker color="teal" data-testid="m">text</Marker>);
    expect(screen.getByTestId("m").className).toContain("marker--teal");
  });

  it("applies berry color variant", () => {
    render(<Marker color="berry" data-testid="m">text</Marker>);
    expect(screen.getByTestId("m").className).toContain("marker--berry");
  });
});
