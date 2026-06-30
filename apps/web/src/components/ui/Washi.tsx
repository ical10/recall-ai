import { cn } from "./cn";

type WashiColor = "honey" | "teal" | "berry" | "sky";

export function Washi({
  color = "honey",
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { color?: WashiColor }) {
  return (
    <div
      className={cn(
        "washi",
        color === "teal" && "washi--teal",
        color === "berry" && "washi--berry",
        color === "sky" && "washi--sky",
        className,
      )}
      {...props}
    />
  );
}
