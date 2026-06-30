export function cn(...classes: (string | false | undefined | null | number)[]): string {
  return classes.filter(Boolean).join(" ");
}
