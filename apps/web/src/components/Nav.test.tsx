import type { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Nav } from "@/components/Nav";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    children,
    ...props
  }: { to: string; children?: ReactNode } & Record<string, unknown>) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

import { useQuery } from "@tanstack/react-query";

describe("Nav", () => {
  it("always shows My Words and Practice when signed in (visible on mobile)", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { id: "1", email: "a@b.com", name: "Ana", avatar_url: null },
      isLoading: false,
    } as never);

    render(<Nav />);

    const myWords = screen.getByRole("link", { name: "My Words" });
    const practice = screen.getByRole("link", { name: "Practice" });

    expect(myWords).toBeInTheDocument();
    expect(practice).toBeInTheDocument();
    expect(myWords.className).not.toMatch(/\bhidden\b/);
    expect(practice.className).not.toMatch(/\bhidden\b/);
  });

  it("shows a quiet Grown-ups link to /grown-ups", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: { id: "1", email: "a@b.com", name: "Ana", avatar_url: null },
      isLoading: false,
    } as never);

    render(<Nav />);

    const grownUps = screen.getByRole("link", { name: "Grown-ups" });
    expect(grownUps).toHaveAttribute("href", "/grown-ups");
  });

  it("does not show signed-in links when logged out", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: null,
      isLoading: false,
    } as never);

    render(<Nav />);

    expect(screen.queryByRole("link", { name: "My Words" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Practice" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Grown-ups" })).not.toBeInTheDocument();
  });

  describe("sign out", () => {
    const originalLocation = window.location;
    let assignMock: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      assignMock = vi.fn();
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: { ...originalLocation, assign: assignMock },
      });

      vi.mocked(useQuery).mockReturnValue({
        data: { id: "1", email: "a@b.com", name: "Ana", avatar_url: null },
        isLoading: false,
      } as never);
    });

    afterEach(() => {
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: originalLocation,
      });
      vi.unstubAllGlobals();
    });

    it("POSTs to /api/auth/logout and redirects to /login", async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true });
      vi.stubGlobal("fetch", fetchMock);

      render(<Nav />);
      fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

      await waitFor(() => expect(assignMock).toHaveBeenCalledWith("/login"));
      expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
      });
    });

    it("still redirects to /login when the logout request rejects", async () => {
      const fetchMock = vi.fn().mockRejectedValue(new Error("network error"));
      vi.stubGlobal("fetch", fetchMock);

      render(<Nav />);
      fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

      await waitFor(() => expect(assignMock).toHaveBeenCalledWith("/login"));
    });
  });
});
