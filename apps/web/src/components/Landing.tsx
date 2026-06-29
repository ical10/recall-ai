import { Link } from "@tanstack/react-router";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Washi } from "@/components/ui/Washi";
import { Chip } from "@/components/ui/Chip";
import { Marker } from "@/components/ui/Marker";

export function Landing() {
  return (
    <main className="relative mx-auto max-w-5xl px-6 pb-24 pt-10">
      <section className="grid gap-10 pt-8 md:grid-cols-5 md:items-center md:gap-6">
        <div className="md:col-span-3">
          <Chip dotColor="bg-teal">Spaced repetition · for ESL</Chip>
          <h1 className="mt-6 font-display text-6xl font-black leading-[0.95] tracking-tight md:text-7xl text-ink">
            Words that{" "}
            <Marker>stick</Marker>.
            <br />
            Memory that{" "}
            <Marker color="teal">grows</Marker>.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-soft">
            A pocket-sized vocabulary trainer that learns how you forget — then
            feeds you the right word at exactly the right moment.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link to="/login">
              <Button variant="primary" glyph="→">
                Start learning
              </Button>
            </Link>
            <Link to="/dashboard">
              <Button variant="ghost">See the deck</Button>
            </Link>
          </div>

          <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm font-medium text-ink-mute">
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-tangerine" />
              LLM-crafted examples
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-teal" />
              SM-2 scheduling
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-sky" />
              Daily nudges
            </span>
          </div>
        </div>

        <div className="relative md:col-span-2">
          <Card size="lg" tilt="r" animate="pop-in" washi={<Washi className="top-[-12px] left-8 tilt-l-2" />}>
            <p className="font-mono text-xs uppercase tracking-widest text-ink-mute">English · Adv.</p>
            <h2 className="mt-3 font-display text-5xl font-black leading-none text-ink">ephemeral</h2>
            <p className="mt-4 leading-snug text-ink-soft">
              Lasting for a very short time.
            </p>
            <p className="mt-3 italic leading-snug text-ink-mute">
              "The cherry blossoms are <Marker>ephemeral</Marker> — gone in a week."
            </p>
            <div className="mt-5 grid grid-cols-4 gap-1.5">
              <span className="rounded-lg border-2 border-ink bg-berry py-1.5 text-center text-[11px] font-bold text-cream-50">Again</span>
              <span className="rounded-lg border-2 border-ink bg-honey py-1.5 text-center text-[11px] font-bold text-ink">Hard</span>
              <span className="rounded-lg border-2 border-ink bg-teal py-1.5 text-center text-[11px] font-bold text-cream-50">Good</span>
              <span className="rounded-lg border-2 border-ink bg-sky py-1.5 text-center text-[11px] font-bold text-cream-50">Easy</span>
            </div>
          </Card>

          <Card tilt="l" className="absolute -bottom-6 -left-2 hidden w-44 sm:block" washi={<Washi color="teal" className="top-[-12px] left-6 tilt-r-2" />}>
            <p className="font-mono text-[10px] uppercase tracking-widest text-ink-mute">Streak</p>
            <p className="mt-1 font-display text-4xl font-black leading-none text-ink">
              12<span className="text-honey">·</span>
            </p>
            <p className="mt-1 text-xs font-medium text-ink-mute">days in a row</p>
          </Card>

          <div aria-hidden="true" className="absolute -right-4 -top-6 h-12 w-12 animate-sparkle rounded-full bg-honey/60 blur-sm" />
        </div>
      </section>

      <section className="mt-28 grid gap-5 sm:grid-cols-3">
        <FeatureCard
          number="1"
          title="Pull"
          description="We surface the cards you're closest to forgetting — never the easy ones."
          color="tangerine"
          tilt="l"
          delay={0}
        />
        <FeatureCard
          number="2"
          title="React"
          description="Rate each card after you reveal it. SM-2 reschedules it to just before you'd forget."
          color="teal"
          delay={150}
        />
        <FeatureCard
          number="3"
          title="Repeat"
          description="A few minutes a day. The algorithm takes it from there."
          color="sky"
          tilt="r"
          delay={300}
        />
      </section>
    </main>
  );
}

function FeatureCard({
  number,
  title,
  description,
  color,
  tilt,
  delay,
}: {
  number: string;
  title: string;
  description: string;
  color: string;
  tilt?: "l" | "r";
  delay: number;
}) {
  const colorMap: Record<string, string> = {
    tangerine: "bg-tangerine text-cream-50",
    teal: "bg-teal text-cream-50",
    sky: "bg-sky text-cream-50",
  };

  return (
    <Card tilt={tilt} animate="rise" style={{ animationDelay: `${delay}ms` }}>
      <span
        className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border-2 border-ink ${colorMap[color] ?? ""} font-display text-sm font-black`}
      >
        {number}
      </span>
      <h3 className="mt-3 font-display text-xl font-black text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-ink-soft">{description}</p>
    </Card>
  );
}
