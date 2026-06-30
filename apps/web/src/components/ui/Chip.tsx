import { cn } from "./cn";

export function Chip({
  children,
  dotColor = "bg-honey",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { dotColor?: string }) {
  return (
    <span className={cn("chip", className)} {...props}>
      <span className={cn("h-1.5 w-1.5 rounded-full", dotColor)} />
      {children}
    </span>
  );
}
