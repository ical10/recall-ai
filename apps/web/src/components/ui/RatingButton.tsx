import { cn } from "./cn";

const RATINGS = {
  0: { emoji: "🙈", label: "Oops!", color: "berry" },
  2: { emoji: "🤔", label: "Tricky!", color: "honey" },
  4: { emoji: "😊", label: "Got it!", color: "teal" },
  5: { emoji: "🔥", label: "So easy!", color: "sky" },
} as const;

export type RatingQuality = keyof typeof RATINGS;

export function RatingButton({
  quality,
  onClick,
  className,
  ...props
}: {
  quality: RatingQuality;
  onClick?: () => void;
  className?: string;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick">) {
  const rating = RATINGS[quality];
  return (
    <button
      aria-label={`${rating.emoji} ${rating.label}`}
      className={cn(
        "btn-pop",
        `btn-pop--${rating.color}`,
        "flex-col py-4",
        className,
      )}
      onClick={onClick}
      type="button"
      {...props}
    >
      <span className="text-2xl">{rating.emoji}</span>
      <span className="text-xs font-bold tracking-wide">{rating.label}</span>
    </button>
  );
}
