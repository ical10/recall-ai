import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";
import { IconBadge } from "@/components/ui/IconBadge";
import { Marker } from "@/components/ui/Marker";
import { SEEN_KEYS, seenOnce } from "@/lib/seen";
import { useReviewSession } from "@/store/reviewSession";

const confettiColors = [
  "bg-tangerine",
  "bg-teal",
  "bg-honey",
  "bg-sky",
  "bg-berry",
  "bg-tangerine",
  "bg-sky",
  "bg-teal",
  "bg-honey",
  "bg-berry",
  "bg-tangerine",
  "bg-sky",
] as const;

const confettiLeft = [
  "8%",
  "18%",
  "28%",
  "38%",
  "48%",
  "58%",
  "68%",
  "78%",
  "88%",
  "23%",
  "53%",
  "83%",
];

export function DoneCard({ count }: { count: number }) {
  const [firstDone] = useState(() => seenOnce(SEEN_KEYS.firstDone));
  const { outbox, flushing, flushRatings } = useReviewSession();
  const confettiCount = firstDone ? 12 : 8;

  useEffect(() => {
    void flushRatings();
  }, [flushRatings]);

  return (
    <Card
      size="lg"
      className="relative overflow-hidden text-center"
      animate="pop-in"
    >
      {confettiColors.slice(0, confettiCount).map((color, index) => (
        <span
          key={`${color}-${index}`}
          aria-hidden="true"
          className={`confetti-dot ${color}`}
          style={{
            left: confettiLeft[index],
            top: "0.5rem",
            animationDelay: `${index * 80}ms`,
          }}
        />
      ))}

      <IconBadge size="lg" color="bg-teal" className="mx-auto animate-wiggle">
        <Icon name="check" className="h-10 w-10 text-cream-50" />
      </IconBadge>

      <h1 className="mt-6 font-display text-5xl font-black leading-none tracking-tight text-ink">
        <Marker color="teal">You did it!</Marker>
      </h1>
      {firstDone ? (
        <div className="mt-4 space-y-1 text-lg text-ink-soft">
          <p>You learned your first words!</p>
          <p>Come back tomorrow. They will wait for you!</p>
        </div>
      ) : (
        <p className="mt-4 text-lg text-ink-soft">
          {count} words done today! 🎉
        </p>
      )}

      {(flushing || outbox.length > 0) && (
        <p className="mt-4 text-sm font-medium text-ink-soft" aria-live="polite">
          Saving…
        </p>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link to="/dashboard" className="btn-pop btn-pop--ink text-base">
          Go to My Words
        </Link>
        <Link to="/dashboard" className="btn-pop btn-pop--ghost text-base">
          Add a new word
        </Link>
      </div>
    </Card>
  );
}
