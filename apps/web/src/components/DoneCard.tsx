import { Card } from "@/components/ui/Card";
import { IconBadge } from "@/components/ui/IconBadge";
import { Marker } from "@/components/ui/Marker";
import { Icon } from "@/components/ui/Icon";

const confettiColors = [
  "bg-tangerine", "bg-teal", "bg-honey", "bg-sky",
  "bg-berry", "bg-tangerine", "bg-sky", "bg-teal",
] as const;

const confettiLeft = ["10%", "25%", "40%", "55%", "70%", "85%", "18%", "62%"];
const confettiDelay = [0, 120, 240, 80, 320, 200, 440, 380];

export function DoneCard() {
  return (
    <Card size="lg" className="relative overflow-hidden text-center" animate="pop-in">
      {confettiColors.map((color, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={`confetti-dot ${color}`}
          style={{ left: confettiLeft[i], top: "0.5rem", animationDelay: `${confettiDelay[i]}ms` }}
        />
      ))}

      <IconBadge size="lg" color="bg-teal" className="mx-auto animate-wiggle">
        <Icon name="check" className="h-10 w-10 text-cream-50" />
      </IconBadge>

      <h1 className="mt-6 font-display text-5xl font-black leading-none tracking-tight text-ink">
        <Marker color="teal">All caught up</Marker>.
      </h1>
      <p className="mt-4 text-lg text-ink-soft">
        No more cards to review today.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <a href="/dashboard" className="btn-pop btn-pop--ink text-base">
          Back to deck
        </a>
        <a href="/dashboard" className="btn-pop btn-pop--ghost text-base">
          Add a new word
        </a>
      </div>
    </Card>
  );
}
