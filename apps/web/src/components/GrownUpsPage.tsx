import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { fetchApi } from "@/api/client";
import type { components } from "@/api/schema";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/StatCard";
import { IntervalCard } from "@/components/IntervalCard";

type UserStats = components["schemas"]["UserStats"];

export function GrownUpsPage() {
  const { data, isLoading, error, refetch } = useQuery<UserStats>({
    queryKey: ["dashboard"],
    queryFn: (): Promise<UserStats> => fetchApi<UserStats>("/api/dashboard"),
  });

  if (isLoading) return <GrownUpsSkeleton />;

  if (error) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-8">
        <Card className="text-center" tilt="l">
          <p className="font-medium text-ink-soft">
            Couldn&apos;t load the stats. Try again.
          </p>
          <Button variant="ink" className="mt-4" onClick={() => refetch()}>
            Try again
          </Button>
        </Card>
      </main>
    );
  }

  if (!data) return null;

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="mb-2 font-display text-5xl font-black tracking-tight text-ink">
        For grown-ups
      </h1>
      <p className="mb-8 text-ink-soft">How practice is going.</p>

      <div className="mb-8 grid grid-cols-3 gap-4">
        <StatCard
          label="Due today"
          value={data.due_today}
          subtitle="words to practice"
          icon="clock"
          tilt="l"
          delay={0}
        />
        <StatCard
          label="Total reviews"
          value={data.total_reviews}
          subtitle="all time"
          icon="check"
          tilt="r"
          delay={100}
        />
        <StatCard
          label="Streak"
          value={data.current_streak}
          subtitle={`${data.current_streak} days in a row`}
          icon="flame"
          tilt="l-2"
          delay={200}
        />
      </div>

      <section className="mt-8">
        <h2 className="mb-3 font-display text-2xl font-black text-ink">
          Review history
        </h2>
        {data.recent.length === 0 ? (
          <Card>
            <p className="text-ink-mute">No reviews yet.</p>
          </Card>
        ) : (
          <ul className="space-y-2">
            {data.recent.map((r, i) => (
              <IntervalCard key={i} review={r} index={i} />
            ))}
          </ul>
        )}
      </section>

      <div className="mt-8">
        <Link
          to="/archive"
          className="text-sm font-semibold text-ink underline decoration-tangerine decoration-2 underline-offset-4 hover:text-tangerine"
        >
          See all words →
        </Link>
      </div>

      <p className="mt-10 text-xs text-ink-mute">
        Microphone is off? Turn it on in your browser settings to check pronunciation.
      </p>
    </main>
  );
}

function GrownUpsSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="mb-8 h-12 w-64 rounded bg-cream-200" />
      <div className="mb-8 grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 rounded-2xl bg-cream-200" />
        ))}
      </div>
      <div className="h-40 rounded-2xl bg-cream-200" />
    </main>
  );
}
