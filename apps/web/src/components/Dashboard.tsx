import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { fetchApi } from "@/api/client";
import type { components } from "@/api/schema";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Marker } from "@/components/ui/Marker";
import { StartSticker } from "@/components/StartSticker";
import { StickerShelf } from "@/components/StickerShelf";
import { AddWordCard, type AddWordCardHandle } from "@/components/AddWordCard";

type UserStats = components["schemas"]["UserStats"];

export function Dashboard() {
  const { data, isLoading, error, refetch } = useQuery<UserStats>({
    queryKey: ["dashboard"],
    queryFn: (): Promise<UserStats> => fetchApi<UserStats>("/api/dashboard"),
  });
  const addWordRef = useRef<AddWordCardHandle>(null);

  if (isLoading) return <DashboardSkeleton />;
  if (error) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-8">
        <div role="alert" className="tilt-l card-paper--lg text-center">
          <p className="font-display text-2xl font-black text-ink">
            Your words did not load.
          </p>
          <Button variant="ink" className="mt-5" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      </main>
    );
  }
  if (!data) return null;

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-5xl font-display font-black tracking-tight text-ink mb-8">
        <Marker>My Words</Marker>
      </h1>

      <StartSticker dueCount={data.due_today} streak={data.current_streak} />

      {data.unseen_milestone && (
        <div className="mt-8">
          <MilestoneBanner milestone={data.unseen_milestone} />
        </div>
      )}

      <div className="mt-10">
        <StickerShelf onEmptyCta={() => addWordRef.current?.expandAndFocus()} />
      </div>

      <div className="mt-8">
        <AddWordCard ref={addWordRef} />
      </div>
    </main>
  );
}

function MilestoneBanner({ milestone }: { milestone: number }) {
  const navigate = useNavigate();

  return (
    <Card className="bg-honey-light !border-honey text-center" animate="pop-in">
      <p className="font-display text-2xl font-black text-ink">
        You practiced {milestone} times! ⭐
      </p>
      <p className="mt-1 text-ink-soft font-medium">You are a star!</p>
      <Button
        variant="ink"
        className="mt-4"
        onClick={async () => {
          await fetchApi("/api/milestones/seen", { method: "POST" });
          navigate({ to: "/review" });
        }}
      >
        Keep going!
      </Button>
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="h-12 bg-cream-200 rounded w-48 mb-8" />
      <div className="min-h-[240px] rounded-[28px] bg-cream-200 tilt-r-2 mb-10" />
      <div className="h-8 bg-cream-200 rounded w-40 mb-4" />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 mb-8">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className={`min-h-[120px] rounded-2xl bg-cream-200 ${i % 2 === 0 ? "tilt-l" : "tilt-r"}`}
          />
        ))}
      </div>
      <div className="h-24 bg-cream-200 rounded-3xl tilt-l" />
    </main>
  );
}
