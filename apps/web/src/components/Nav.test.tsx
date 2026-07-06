import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Nav } from "@/components/Nav";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useQueryClient: vi.fn(() => ({ clear: vi.fn() })),
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
  useNavigate: () => vi.fn(),
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
});
