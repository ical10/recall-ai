import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchApi } from "@/api/client";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Marker } from "@/components/ui/Marker";

interface VocabItem {
  id: string;
  token: string;
  language: string;
  part_of_speech: string | null;
  definition: string;
  example_sentence: string | null;
}

interface VocabListResponse {
  items: VocabItem[];
  page: number;
  page_size: number;
  total: number;
}

export function ArchivePage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading, error } = useQuery<VocabListResponse>({
    queryKey: ["archive", page],
    queryFn: (): Promise<VocabListResponse> =>
      fetchApi<VocabListResponse>(`/api/archive?page=${page}&page_size=${pageSize}`),
  });

  if (isLoading) return <ArchiveSkeleton />;
  if (error) return <div className="p-8 text-berry">Failed to load archive</div>;
  if (!data) return null;

  const totalPages = Math.ceil(data.total / pageSize);

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-5xl font-display font-black tracking-tight text-ink mb-8">
        <Marker>Archive</Marker>
      </h1>

      {data.items.length === 0 ? (
        <Card>
          <p className="text-ink-mute">No vocabulary items yet.</p>
        </Card>
      ) : (
        <>
          <ul className="space-y-3 mb-6">
            {data.items.map((item, i) => (
              <li
                key={item.id}
                className="card-paper !p-4"
                style={i % 2 === 0 ? { transform: "rotate(-1.5deg)" } : { transform: "rotate(1.5deg)" }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-display text-lg font-black text-ink">{item.token}</span>
                    <Chip dotColor="bg-sky">{item.language}</Chip>
                  </div>
                </div>
                <p className="text-sm text-ink-soft mt-1">{item.definition}</p>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-center gap-4">
            <Button
              variant="ghost"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              Previous
            </Button>
            <span className="text-sm text-ink-mute font-mono">
              {page} / {totalPages}
            </span>
            <Button
              variant="ghost"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </main>
  );
}

function ArchiveSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="h-10 bg-cream-200 rounded w-32 mb-8" />
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-16 bg-cream-200 rounded-xl mb-3" />
      ))}
    </main>
  );
}
