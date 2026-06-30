import { Link } from "@tanstack/react-router";
import { Card } from "@/components/ui/Card";
import { Washi } from "@/components/ui/Washi";
import { Marker } from "@/components/ui/Marker";
import { Eyebrow } from "@/components/ui/Eyebrow";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

function FloatingShape({ className }: { className: string }) {
  return (
    <span
      aria-hidden="true"
      className={`absolute border-2 border-ink shadow-pop-sm ${className}`}
    />
  );
}

export function LoginPage() {
  return (
    <main className="relative flex min-h-[calc(100vh-88px)] items-center justify-center px-6 pb-12">
      <FloatingShape className="left-[12%] top-20 h-16 w-16 rotate-12 rounded-2xl bg-honey" />
      <FloatingShape className="right-[10%] top-32 h-12 w-12 -rotate-6 rounded-full bg-teal" />
      <FloatingShape className="bottom-24 left-[18%] h-10 w-20 rotate-6 rounded-xl bg-sky" />

      <div className="relative w-full max-w-md">
        <Card size="lg" tilt="l-2" animate="pop-in" washi={<Washi color="berry" className="-top-4 left-12 tilt-r-2" />}>
          <Eyebrow>Spaced-repetition vocabulary</Eyebrow>
          <h1 className="mt-3 font-display text-5xl font-black leading-[0.95] text-ink">
            Words that <Marker>stick</Marker>.
          </h1>
          <p className="mt-4 leading-relaxed text-ink-soft">
            Catch each new word right before you forget it — your deck and streak
            are waiting.
          </p>

          <div className="mt-7">
            <GoogleSignInButton />
          </div>

          <p className="mt-5 text-center text-xs text-ink-mute">
            We only see your name and email. No noise.
          </p>
        </Card>

        <p className="mt-8 text-center text-sm font-medium text-ink-mute">
          New here?{" "}
          <Link
            to="/about"
            className="text-ink underline decoration-tangerine decoration-2 underline-offset-4 hover:text-tangerine"
          >
            Read what Recall is →
          </Link>
        </p>
      </div>
    </main>
  );
}
