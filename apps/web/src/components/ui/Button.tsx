import { cn } from "./cn";

type ButtonVariant =
  | "primary"
  | "ink"
  | "teal"
  | "berry"
  | "honey"
  | "sky"
  | "ghost";

type ButtonProps = {
  variant?: ButtonVariant;
  fullWidth?: boolean;
  glyph?: string;
  as?: "button" | "a";
  href?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement> &
  React.AnchorHTMLAttributes<HTMLAnchorElement>;

export function Button({
  variant = "primary",
  fullWidth,
  glyph,
  as = "button",
  href,
  className,
  children,
  ...props
}: ButtonProps) {
  const classes = cn(
    "btn-pop",
    `btn-pop--${variant}`,
    fullWidth && "w-full",
    className,
  );

  if (as === "a") {
    return (
      <a href={href} className={classes} {...(props as React.AnchorHTMLAttributes<HTMLAnchorElement>)}>
        {children}
        {glyph && <span>{glyph}</span>}
      </a>
    );
  }

  return (
    <button
      className={classes}
      {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      {children}
      {glyph && <span>{glyph}</span>}
    </button>
  );
}
