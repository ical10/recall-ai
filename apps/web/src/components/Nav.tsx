import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";
import { Button } from "@/components/ui/Button";

interface MeResponse {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
}

export function Nav() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user, isLoading } = useQuery<MeResponse | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await fetchApi<MeResponse>("/api/me");
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
    retry: false,
  });

  const handleLogout = async () => {
    await fetchApi("/api/auth/logout", { method: "POST" });
    queryClient.clear();
    navigate({ to: "/login" });
  };

  return (
    <nav className="relative z-10">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <Link
          to={user ? "/dashboard" : "/"}
          className="group inline-flex items-center gap-2.5"
        >
          <span className="relative inline-flex h-10 w-10 items-center justify-center rounded-2xl border-2 border-ink bg-tangerine shadow-pop-sm transition-transform group-hover:-rotate-6">
            <span className="font-display text-xl font-black text-cream-50">R</span>
            <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-ink bg-honey" />
          </span>
          <span className="font-display text-2xl font-black tracking-tight text-ink">
            Recall<span className="text-tangerine">.ai</span>
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            to="/about"
            className="hidden text-sm font-semibold text-ink-mute hover:text-ink sm:inline"
          >
            About
          </Link>
          {user && !isLoading ? (
            <>
              <Link
                to="/dashboard"
                className="hidden text-sm font-semibold text-ink-mute hover:text-ink sm:inline"
              >
                Deck
              </Link>
              <Link
                to="/review"
                className="hidden text-sm font-semibold text-ink-mute hover:text-ink sm:inline"
              >
                Review
              </Link>
              <Link
                to="/settings"
                className="hidden text-sm font-semibold text-ink-mute hover:text-ink sm:inline"
              >
                Settings
              </Link>
              <span className="hidden h-6 w-px bg-ink/15 sm:inline-block" />
              <span className="hidden text-sm font-medium text-ink-soft sm:inline">
                {user.name}
              </span>
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border-2 border-ink bg-lavender font-display text-sm font-bold text-ink">
                {user.name.charAt(0).toUpperCase()}
              </span>
              <button
                onClick={handleLogout}
                className="text-xs font-bold uppercase tracking-wider text-ink-mute hover:text-berry"
              >
                Sign out
              </button>
            </>
          ) : (
            <a href="/auth/login-page">
              <Button variant="ink" className="text-sm !py-2 !px-4">
                Sign in
              </Button>
            </a>
          )}
        </div>
      </div>
    </nav>
  );
}
