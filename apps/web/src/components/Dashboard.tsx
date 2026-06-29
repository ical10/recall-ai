import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";
import type { components } from "@/api/schema";

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
      <h1 className="text-3xl font-display font-bold text-ink mb-8">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard label="Due Today" value={data.due_today} color="tangerine" />
        <StatCard label="Total Reviews" value={data.total_reviews} color="teal" />
        <StatCard label="Streak" value={data.current_streak} color="berry" suffix="days" />
      </div>

      {data.unseen_milestone && (
        <div className="bg-honey-light border-2 border-honey rounded-2xl p-4 mb-6 shadow-pop-sm">
          <p className="text-ink-soft font-medium">
            Milestone unlocked: {data.unseen_milestone} reviews!
          </p>
        </div>
      )}

      {data.recent.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-ink-soft mb-3">Recent Reviews</h2>
          <ul className="space-y-2">
            {data.recent.map((r, i) => (
              <li key={i} className="flex items-center justify-between bg-white border border-cream-300 rounded-xl px-4 py-3">
                <span className="font-medium text-ink">{r.token}</span>
                <span className="text-sm text-ink-mute">{r.interval_days}d</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function StatCard({ label, value, color, suffix }: {
  label: string;
  value: number;
  color: string;
  suffix?: string;
}) {
  const colorMap: Record<string, string> = {
    tangerine: "border-tangerine bg-tangerine-light",
    teal: "border-teal bg-teal-light",
    berry: "border-berry bg-berry-light",
  };
  return (
    <div className={`border-2 ${colorMap[color] ?? ""} rounded-2xl p-4 text-center`}>
      <div className="text-3xl font-display font-bold text-ink">
        {value}{suffix ? <span className="text-lg ml-1 text-ink-mute">{suffix}</span> : null}
      </div>
      <div className="text-sm text-ink-mute mt-1">{label}</div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="h-10 bg-cream-200 rounded w-48 mb-8" />
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-cream-200 rounded-2xl" />
        ))}
      </div>
    </main>
  );
}
