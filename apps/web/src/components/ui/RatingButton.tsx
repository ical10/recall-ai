import { cn } from "./cn";

type RatingColor = "berry" | "honey" | "teal" | "sky";

export function RatingButton({
  emoji,
  label,
  quality,
  color,
  onClick,
  className,
  ...props
}: {
  emoji: string;
  label: string;
  quality: number;
  color: RatingColor;
  onClick?: () => void;
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn("btn-pop", `btn-pop--${color}`, "flex-col py-4", className)}
      onClick={onClick}
      type="button"
      {...props}
    >
      <span className="text-2xl">{emoji}</span>
      <span className="text-[10px] font-bold uppercase tracking-widest">{label}</span>
    </button>
  );
}
