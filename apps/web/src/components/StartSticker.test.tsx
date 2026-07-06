import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StartSticker } from "@/components/StartSticker";

const navigateMock = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigateMock,
}));

beforeEach(() => {
  navigateMock.mockClear();
  localStorage.clear();
});

describe("StartSticker", () => {
  it("renders due count and navigates to /review on click when due>0", () => {
    render(<StartSticker dueCount={5} streak={0} />);

    expect(screen.getByText("Start!")).toBeInTheDocument();
    expect(screen.getByText("5 words ready 🎯")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button"));
    expect(navigateMock).toHaveBeenCalledWith({ to: "/review" });
  });

  it("renders done celebration and does not navigate when due=0", () => {
    render(<StartSticker dueCount={0} streak={0} />);

    expect(screen.getByText("All done today! 🎉")).toBeInTheDocument();
    expect(screen.getByText("Come back tomorrow.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("hides streak chip when streak < 2", () => {
    render(<StartSticker dueCount={3} streak={1} />);
    expect(screen.queryByText(/days! 🔥/)).not.toBeInTheDocument();
  });

  it("shows streak chip when streak >= 2", () => {
    render(<StartSticker dueCount={3} streak={4} />);
    expect(screen.getByText("4 days! 🔥")).toBeInTheDocument();
  });
});
