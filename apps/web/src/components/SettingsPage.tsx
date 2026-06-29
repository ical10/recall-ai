import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";
import { Marker } from "@/components/ui/Marker";
import { Eyebrow } from "@/components/ui/Eyebrow";
import { Card } from "@/components/ui/Card";

interface UserSettings {
  interest_tags: string[];
  all_tags: string[];
}

export function SettingsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<UserSettings>({
    queryKey: ["settings"],
    queryFn: (): Promise<UserSettings> =>
      fetchApi<UserSettings>("/api/settings"),
  });

  const mutation = useMutation<UserSettings, Error, string[]>({
    mutationFn: (tags) =>
      fetchApi<UserSettings>("/api/settings/interests", {
        method: "PUT",
        body: JSON.stringify({ tags }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  if (isLoading) return <SettingsSkeleton />;
  if (error) return <div className="p-8 text-berry">Failed to load settings</div>;
  if (!data) return null;

  const selected = new Set(data.interest_tags);

  const toggle = (tag: string) => {
    const next = selected.has(tag)
      ? data.interest_tags.filter((t) => t !== tag)
      : [...data.interest_tags, tag];
    mutation.mutate(next);
  };

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-5xl font-display font-black tracking-tight text-ink mb-8">
        <Marker>Settings</Marker>
      </h1>

      <Card>
        <Eyebrow className="mb-4 block">Interest Tags</Eyebrow>
        <div className="flex flex-wrap gap-2">
          {data.all_tags.map((tag) => {
            const active = selected.has(tag);
            return (
              <label
                key={tag}
                className={`inline-flex items-center gap-1.5 rounded-full border-2 px-3 py-1.5 text-xs font-bold uppercase tracking-wider cursor-pointer select-none transition-colors ${
                  active
                    ? "border-ink bg-cream-50 text-ink"
                    : "border-cream-300 bg-transparent text-ink-mute hover:border-ink-mute"
                }`}
              >
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggle(tag)}
                  disabled={mutation.isPending}
                  className="sr-only"
                />
                {tag.replace(/_/g, " ")}
                {active && (
                  <span className="ml-0.5 text-[9px]">&#10003;</span>
                )}
              </label>
            );
          })}
        </div>
        {mutation.isSuccess && (
          <p className="mt-4 text-sm font-medium text-teal">Saved</p>
        )}
      </Card>
    </main>
  );
}

function SettingsSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="h-10 bg-cream-200 rounded w-48 mb-8" />
      <div className="flex flex-wrap gap-2">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="h-10 w-24 bg-cream-200 rounded-xl" />
        ))}
      </div>
    </main>
  );
}
