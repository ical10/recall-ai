import { Icon } from "@/components/ui/Icon";

export function GoogleSignInButton({ className }: { className?: string }) {
  return (
    <a
      href="/auth/login"
      className={`btn-pop btn-pop--ink w-full text-base ${className ?? ""}`}
    >
      <Icon name="google" className="h-5 w-5" />
      Sign in with Google
    </a>
  );
}
