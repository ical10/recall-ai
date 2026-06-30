import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";
import { Card } from "@/components/ui/Card";
import { Washi } from "@/components/ui/Washi";
import { Marker } from "@/components/ui/Marker";
import { Eyebrow } from "@/components/ui/Eyebrow";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

interface MeResponse {
  id: string;
  name: string;
}

function FloatingShape({ className }: { className: string }) {
  return (
    <span
      aria-hidden="true"
      className={`absolute border-2 border-ink shadow-pop-sm ${className}`}
    />
  );
}

export function AboutPage() {
  const { data: user } = useQuery<MeResponse | null>({
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

  return (
    <main className="relative flex min-h-[calc(100vh-88px)] items-center justify-center px-6 pb-12">
      <FloatingShape className="left-[10%] top-24 h-14 w-14 rotate-12 rounded-2xl bg-honey" />
      <FloatingShape className="right-[12%] top-40 h-10 w-10 -rotate-6 rounded-full bg-teal" />
      <FloatingShape className="bottom-28 left-[16%] h-9 w-16 rotate-6 rounded-xl bg-sky" />

      <div className="relative w-full max-w-xl">
        <Card size="lg" tilt="l-2" animate="pop-in" washi={<Washi color="berry" className="-top-4 left-12 tilt-r-2" />}>
          <Eyebrow>How it works</Eyebrow>
          <h1 className="mt-3 font-display text-5xl font-black leading-[0.95] text-ink">
            Words that <Marker>stick</Marker> — by design.
          </h1>

          <p className="mt-6 leading-relaxed text-ink-soft">
            Show up. Rate the card. Move on.{" "}
            <strong>SM-2</strong> — the same algorithm Anki uses — decides when
            each word comes back. Easy ones slide weeks out. Hard ones return
            tomorrow.
          </p>

          <p className="mt-4 leading-relaxed text-ink-soft">
            Every night, an AI bakes fresh cards from topics you actually care
            about. Five minutes a day. The words stick — because you caught them
            right before you forgot.
          </p>

          {!user ? (
            <>
              <p className="mt-5 font-semibold text-ink">
                Sign in below — let's see what sticks.
              </p>
              <div className="mt-7">
                <GoogleSignInButton />
              </div>
            </>
          ) : (
            <Link to="/dashboard" className="btn-pop btn-pop--ink mt-7 w-full text-base inline-flex">
              Open your deck →
            </Link>
          )}
        </Card>

        {!user && (
          <p className="mt-8 text-center text-sm font-medium text-ink-mute">
            Already have an account?{" "}
            <Link
              to="/login"
              className="text-ink underline decoration-tangerine decoration-2 underline-offset-4 hover:text-tangerine"
            >
              Sign in →
            </Link>
          </p>
        )}
      </div>
    </main>
  );
}
