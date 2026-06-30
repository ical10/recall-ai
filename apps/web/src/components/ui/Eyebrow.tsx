import { cn } from "./cn";

export function Eyebrow({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "font-mono text-[11px] uppercase tracking-[0.22em] text-ink-mute",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
