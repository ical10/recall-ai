import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Washi } from "@/components/ui/Washi";
import { Marker } from "@/components/ui/Marker";
import { Eyebrow } from "@/components/ui/Eyebrow";
import { IconBadge } from "@/components/ui/IconBadge";
import { Icon } from "@/components/ui/Icon";

type Phase = "collapsed" | "form" | "added" | "exists" | "failure";

export interface AddWordCardHandle {
  expandAndFocus: () => void;
}

export const AddWordCard = forwardRef<AddWordCardHandle>(function AddWordCard(_props, ref) {
  const [phase, setPhase] = useState<Phase>("collapsed");
  const [token, setToken] = useState("");
  const [submittedToken, setSubmittedToken] = useState("");
  const [pending, setPending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const expand = () => {
    setPhase("form");
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  useImperativeHandle(ref, () => ({ expandAndFocus: expand }));

  const backToForm = () => {
    setToken("");
    setPhase("form");
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const submit = async () => {
    const t = token.trim();
    if (!t) return;
    setPending(true);
    setSubmittedToken(t);

    try {
      const resp = await fetch("/vocab", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: t, language: "en" }),
      });
      if (!resp.ok) {
        setPhase("failure");
        return;
      }
      const data = await resp.json();
      setPhase(data.definition === "" ? "added" : "exists");
    } catch {
      setPhase("failure");
    } finally {
      setPending(false);
    }
  };

  if (phase === "collapsed") {
    return (
      <Card tilt="l" washi={<Washi color="sky" className="-top-3 left-8 tilt-r-2" />}>
        <button type="button" onClick={expand} className="flex w-full items-center gap-4 text-left">
          <IconBadge color="bg-sky" className="shrink-0">
            <span className="font-display text-xl font-black text-cream-50">+</span>
          </IconBadge>
          <span className="font-display text-2xl font-black tracking-tight text-ink">
            Add a new word
          </span>
        </button>
      </Card>
    );
  }

  if (phase === "added") {
    return (
      <Card tilt="r" animate="pop-in" washi={<Washi color="teal" className="-top-3 right-8 tilt-l-2" />}>
        <div className="flex items-start gap-4">
          <IconBadge color="bg-teal" className="shrink-0">
            <Icon name="check" className="h-6 w-6 text-cream-50" />
          </IconBadge>
          <div>
            <p className="font-display text-3xl font-black leading-tight text-ink">
              You added <Marker color="teal">{submittedToken}</Marker>!
            </p>
            <p className="mt-2 text-ink-soft">It is ready to practice!</p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link to="/review" className="btn-pop btn-pop--ink text-sm">
            Practice now
          </Link>
          <Button variant="ghost" onClick={backToForm} className="text-sm">
            Add another word
          </Button>
        </div>
      </Card>
    );
  }

  if (phase === "exists") {
    return (
      <Card tilt="l" animate="pop-in" washi={<Washi color="honey" className="-top-3 right-8 tilt-r-2" />}>
        <div className="flex items-start gap-4">
          <IconBadge color="bg-honey" className="shrink-0">
            <Icon name="info" className="h-6 w-6 text-ink" />
          </IconBadge>
          <div>
            <Eyebrow>{submittedToken}</Eyebrow>
            <p className="mt-1 font-display text-2xl font-black leading-tight text-ink">
              You already have this word!
            </p>
          </div>
        </div>
        <div className="mt-5">
          <Button variant="ghost" onClick={backToForm} className="text-sm">
            Try another word
          </Button>
        </div>
      </Card>
    );
  }

  if (phase === "failure") {
    return (
      <Card
        tilt="r"
        animate="pop-in"
        washi={<Washi color="berry" className="-top-3 right-8 tilt-l-2" />}
        role="alert"
      >
        <div className="flex items-start gap-4">
          <IconBadge color="bg-berry" className="shrink-0">
            <Icon name="info" className="h-6 w-6 text-cream-50" />
          </IconBadge>
          <div>
            <p className="font-display text-2xl font-black leading-tight text-ink">
              We could not add your word.
            </p>
          </div>
        </div>
        <div className="mt-5">
          <Button variant="ink" onClick={() => setPhase("form")} className="text-sm">
            Try again
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card tilt="l" animate="pop-in" washi={<Washi color="sky" className="-top-3 left-8 tilt-r-2" />}>
      <h2 className="font-display text-2xl font-black tracking-tight text-ink">Add a new word</h2>

      <label className="mt-5 block">
        <span className="text-xs font-bold uppercase tracking-wider text-ink-soft">
          Your word
        </span>
        <input
          ref={inputRef}
          type="text"
          required
          minLength={1}
          maxLength={255}
          autoComplete="off"
          placeholder="rainbow"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          className="mt-1.5 w-full rounded-2xl border-2 border-ink bg-cream-50 px-4 py-3 font-display text-xl font-bold text-ink placeholder:font-sans placeholder:text-base placeholder:font-normal placeholder:text-ink-mute/60 focus:outline-none focus:ring-4 focus:ring-tangerine/30"
        />
      </label>

      <Button
        variant="primary"
        fullWidth
        className="mt-6"
        onClick={submit}
        disabled={pending || !token.trim()}
      >
        {pending ? "Adding…" : "Add my word"}
      </Button>
    </Card>
  );
});
