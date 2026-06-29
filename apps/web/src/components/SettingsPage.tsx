import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";

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
      <h1 className="text-3xl font-display font-bold text-ink mb-8">Settings</h1>

      <section>
        <h2 className="text-lg font-semibold text-ink-soft mb-4">
          Interest Tags
        </h2>
        <div className="flex flex-wrap gap-2">
          {data.all_tags.map((tag) => {
            const active = selected.has(tag);
            return (
              <button
                key={tag}
                onClick={() => toggle(tag)}
                disabled={mutation.isPending}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors border-2 ${
                  active
                    ? "bg-tangerine text-white border-tangerine"
                    : "bg-white text-ink-mute border-cream-300 hover:border-tangerine"
                }`}
              >
                {tag}
              </button>
            );
          })}
        </div>
      </section>
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
