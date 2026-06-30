import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Washi } from "@/components/ui/Washi";
import { Marker } from "@/components/ui/Marker";
import { Eyebrow } from "@/components/ui/Eyebrow";
import { IconBadge } from "@/components/ui/IconBadge";
import { Icon } from "@/components/ui/Icon";

type Phase = "form" | "added" | "exists";

export function AddWordCard() {
  const [phase, setPhase] = useState<Phase>("form");
  const [token, setToken] = useState("");
  const [submittedToken, setSubmittedToken] = useState("");
  const [pending, setPending] = useState(false);

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
      const data = await resp.json();
      if (data.definition === "") {
        setPhase("added");
      } else {
        setPhase("exists");
      }
    } catch {
      setPhase("form");
    } finally {
      setPending(false);
    }
  };

  const reset = () => {
    setPhase("form");
    setToken("");
  };

  if (phase === "added") {
    return (
      <Card tilt="r" animate="pop-in" washi={<Washi color="teal" className="-top-3 right-8 tilt-l-2" />}>
        <div className="flex items-start gap-4">
          <IconBadge color="bg-teal" className="text-cream-50 shrink-0">
            <Icon name="check" className="h-6 w-6 text-cream-50" />
          </IconBadge>
          <div>
            <Eyebrow>Added · due now</Eyebrow>
            <p className="mt-1 font-display text-3xl font-black leading-tight">
              <Marker color="teal">{submittedToken}</Marker>
            </p>
            <p className="mt-2 text-sm text-ink-mute">
              Sitting in your queue. Open review when you're ready.
            </p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <a href="/review" className="btn-pop btn-pop--ink text-sm">
            Review now
          </a>
          <Button variant="ghost" onClick={reset} className="text-sm">
            Add another
          </Button>
        </div>
      </Card>
    );
  }

  if (phase === "exists") {
    return (
      <Card tilt="l" animate="pop-in" washi={<Washi color="berry" className="-top-3 right-8 tilt-r-2" />}>
        <div className="flex items-start gap-4">
          <IconBadge color="bg-honey" className="text-ink shrink-0">
            <Icon name="info" className="h-6 w-6 text-ink" />
          </IconBadge>
          <div>
            <Eyebrow>Already in deck</Eyebrow>
            <p className="mt-1 font-display text-3xl font-black leading-tight">
              <Marker>{submittedToken}</Marker>
            </p>
            <p className="mt-2 text-sm text-ink-mute">
              Nothing to add — this one's already on the rotation.
            </p>
          </div>
        </div>
        <div className="mt-5">
          <Button variant="ghost" onClick={reset} className="text-sm">
            Try a different word
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card tilt="l" washi={<Washi color="sky" className="-top-3 left-8 tilt-r-2" />}>
      <Eyebrow>Stash a word</Eyebrow>
      <h2 className="mt-1 font-display text-3xl font-black tracking-tight text-ink">
        Add to your <Marker>deck</Marker>
      </h2>

      <label className="mt-5 block">
        <span className="text-xs font-bold uppercase tracking-wider text-ink-soft">
          Word or phrase
        </span>
        <input
          type="text"
          required
          minLength={1}
          maxLength={255}
          autoComplete="off"
          placeholder="ephemeral"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          className="mt-1.5 w-full rounded-2xl border-2 border-ink bg-cream-50 px-4 py-3 font-display text-xl font-bold text-ink placeholder:font-sans placeholder:text-base placeholder:font-normal placeholder:text-ink-mute/60 focus:outline-none focus:ring-4 focus:ring-tangerine/30"
        />
      </label>

      <Button
        variant="primary"
        fullWidth
        glyph="+"
        className="mt-6"
        onClick={submit}
        disabled={pending || !token.trim()}
      >
        Add to deck
      </Button>
    </Card>
  );
}
