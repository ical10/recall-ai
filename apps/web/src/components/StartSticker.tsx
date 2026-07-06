import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Chip } from "@/components/ui/Chip";
import { cn } from "@/components/ui/cn";
import { SEEN_KEYS, seenOnce } from "@/lib/seen";

export function StartSticker({
  dueCount,
  streak,
}: {
  dueCount: number;
  streak: number;
}) {
  const navigate = useNavigate();
  const [wiggle, setWiggle] = useState(false);

  useEffect(() => {
    if (dueCount <= 0) return undefined;
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;
    if (!seenOnce(SEEN_KEYS.startWiggle)) return undefined;

    const timer = window.setTimeout(() => setWiggle(true), 800);
    return () => window.clearTimeout(timer);
  }, [dueCount]);

  if (dueCount <= 0) {
    return (
      <div className="tilt-l-2 animate-pop-in card-paper--lg !border-teal bg-teal-light text-center">
        <p className="font-display text-4xl font-black leading-tight text-ink">
          All done today! 🎉
        </p>
        <p className="mt-2 text-lg font-medium text-ink-soft">Come back tomorrow.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <button
        type="button"
        onClick={() => navigate({ to: "/review" })}
        className={cn(
          "tilt-r-2 flex min-h-[240px] w-full flex-col items-center justify-center gap-3 rounded-[28px] border-2 border-ink bg-tangerine px-6 py-10 text-cream-50 shadow-pop-lg transition-transform duration-100 hover:-translate-y-0.5 active:translate-y-1 active:shadow-pop",
          wiggle && "animate-wiggle",
        )}
      >
        <span className="font-display text-6xl font-black leading-none">Start!</span>
        <span className="text-xl font-bold">{dueCount} words ready 🎯</span>
      </button>

      {streak >= 2 && <Chip dotColor="bg-honey">{streak} days! 🔥</Chip>}
    </div>
  );
}
