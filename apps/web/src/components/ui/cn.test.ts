import { describe, expect, it } from "vitest";
import { cn } from "./cn";

describe("cn", () => {
  it("joins string arguments", () => {
    expect(cn("a", "b", "c")).toBe("a b c");
  });

  it("filters out falsy values", () => {
    expect(cn("a", false, "b", undefined, null, "c", 0, "")).toBe("a b c");
  });

  it("handles a single argument", () => {
    expect(cn("only")).toBe("only");
  });

  it("returns empty string for no valid args", () => {
    expect(cn(false, undefined, null, "")).toBe("");
  });
});
