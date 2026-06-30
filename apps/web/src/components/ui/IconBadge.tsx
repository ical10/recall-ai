import { cn } from "./cn";

type BadgeSize = "sm" | "md" | "lg";

const sizeClasses: Record<BadgeSize, string> = {
  sm: "h-7 w-7 rounded-lg",
  md: "h-10 w-10 rounded-2xl",
  lg: "h-20 w-20 rounded-3xl shadow-pop",
};

export function IconBadge({
  size = "md",
  color,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  size?: BadgeSize;
  color?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex items-center justify-center border-2 border-ink",
        sizeClasses[size],
        color,
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
