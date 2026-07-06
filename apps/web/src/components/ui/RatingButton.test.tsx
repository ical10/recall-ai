import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RatingButton } from "./RatingButton";

describe("RatingButton", () => {
  it.each([
    [0, "🙈 Oops!", "berry"],
    [2, "🤔 Tricky!", "honey"],
    [4, "😊 Got it!", "teal"],
    [5, "🔥 So easy!", "sky"],
  ] as const)("renders grade %i with its label and compass color", (quality, label, color) => {
    render(<RatingButton quality={quality} data-testid="rating" />);
    const button = screen.getByTestId("rating");
    expect(button).toHaveAccessibleName(label);
    expect(button).toHaveClass(`btn-pop--${color}`);
  });

  it("fires onClick", () => {
    const onClick = vi.fn();
    render(<RatingButton quality={5} onClick={onClick} />);
    screen.getByRole("button", { name: "🔥 So easy!" }).click();
    expect(onClick).toHaveBeenCalledOnce();
  });
});
