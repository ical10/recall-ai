import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { fetchApi } from "@/api/client";
import type { components } from "@/api/schema";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Marker } from "@/components/ui/Marker";
import { Eyebrow } from "@/components/ui/Eyebrow";
import { StatCard } from "@/components/StatCard";
import { AddWordCard } from "@/components/AddWordCard";
import { IntervalCard } from "@/components/IntervalCard";

type UserStats = components["schemas"]["UserStats"];

export function Dashboard() {
  const { data, isLoading, error } = useQuery<UserStats>({
    queryKey: ["dashboard"],
    queryFn: (): Promise<UserStats> => fetchApi<UserStats>("/api/dashboard"),
  });

  if (isLoading) return <DashboardSkeleton />;
  if (error) return <div className="p-8 text-berry">Failed to load dashboard</div>;
  if (!data) return null;

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-5xl font-display font-black tracking-tight text-ink mb-8">
        <Marker>Dashboard</Marker>
      </h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard
          label="Due Today"
          value={data.due_today}
          subtitle="cards to review"
          icon="clock"
          tilt="l"
          delay={0}
        />
        <StatCard
          label="Total Reviews"
          value={data.total_reviews}
          subtitle="all time"
          icon="check"
          tilt="r"
          delay={100}
        />
        <StatCard
          label="Streak"
          value={data.current_streak}
          subtitle={`day${data.current_streak === 1 ? "" : "s"} running`}
          icon="flame"
          tilt="l-2"
          delay={200}
        />
      </div>

      {data.unseen_milestone && (
        <MilestoneBanner milestone={data.unseen_milestone} />
      )}

      {data.recent.length > 0 && (
        <section className="mt-8">
          <Eyebrow className="mb-3 block">Recently Reviewed</Eyebrow>
          <ul className="space-y-2">
            {data.recent.map((r, i) => (
              <IntervalCard key={i} review={r} index={i} />
            ))}
          </ul>
        </section>
      )}

      <div className="mt-8">
        <AddWordCard />
      </div>
    </main>
  );
}

function MilestoneBanner({ milestone }: { milestone: number }) {
  const navigate = useNavigate();

  return (
    <Card className="bg-honey-light !border-honey text-center" animate="pop-in">
      <p className="font-display text-2xl font-black text-ink">
        {milestone} reviews!
      </p>
      <p className="mt-1 text-ink-soft font-medium">
        Milestone unlocked
      </p>
      <Button
        variant="ink"
        className="mt-4"
        onClick={async () => {
          await fetchApi("/api/milestones/seen", { method: "POST" });
          navigate({ to: "/review" });
        }}
      >
        Open them
      </Button>
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="h-12 bg-cream-200 rounded w-48 mb-8" />
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-cream-200 rounded-2xl" />
        ))}
      </div>
    </main>
  );
}
