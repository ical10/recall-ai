import { cn } from "./cn";

type MarkerColor = "honey" | "teal" | "berry";

export function Marker({
  children,
  color = "honey",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { color?: MarkerColor }) {
  return (
    <span
      className={cn(
        "marker",
        color === "teal" && "marker--teal",
        color === "berry" && "marker--berry",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
