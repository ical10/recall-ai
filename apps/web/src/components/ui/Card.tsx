import type { ReactNode } from "react";
import { cn } from "./cn";

type TiltDir = "l" | "r" | "l-2" | "r-2";
type AnimateName = "pop-in" | "flip-in" | "rise" | "wiggle" | "sparkle";

export function Card({
  size = "sm",
  tilt,
  animate,
  washi,
  className,
  children,
  ...props
}: {
  size?: "sm" | "lg";
  tilt?: TiltDir;
  animate?: AnimateName;
  washi?: ReactNode;
  className?: string;
  children?: ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  const cardClass = size === "lg" ? "card-paper--lg" : "card-paper";

  return (
    <div
      className={cn(
        cardClass,
        tilt && `tilt-${tilt}`,
        animate && `animate-${animate}`,
        className,
      )}
      {...props}
    >
      {washi}
      {children}
    </div>
  );
}
