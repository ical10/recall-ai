import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchApi } from "@/api/client";

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
      <h1 className="text-3xl font-display font-bold text-ink mb-8">Archive</h1>

      {data.items.length === 0 ? (
        <p className="text-ink-mute">No vocabulary items yet.</p>
      ) : (
        <>
          <ul className="space-y-3 mb-6">
            {data.items.map((item) => (
              <li
                key={item.id}
                className="bg-white border border-cream-300 rounded-xl px-4 py-3"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ink">{item.token}</span>
                  <span className="text-xs text-ink-mute">{item.language}</span>
                </div>
                <p className="text-sm text-ink-soft mt-1">{item.definition}</p>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-4 py-2 text-sm font-medium bg-cream-200 rounded-xl disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-sm text-ink-mute">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages}
              className="px-4 py-2 text-sm font-medium bg-cream-200 rounded-xl disabled:opacity-40"
            >
              Next
            </button>
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
