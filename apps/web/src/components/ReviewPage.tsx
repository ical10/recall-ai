import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";
import { useReviewSession, type Card } from "@/store/reviewSession";

interface DailyBatch {
  cards: Card[];
}

interface SyncResult {
  applied: number;
  skipped: number;
}

// grades match ReviewQuality: AGAIN=0, HARD=2, GOOD=4, EASY=5
const RATINGS = [
  { grade: 0, label: "Again", className: "bg-berry text-white" },
  { grade: 2, label: "Hard", className: "bg-honey text-ink" },
  { grade: 4, label: "Good", className: "bg-teal text-white" },
  { grade: 5, label: "Easy", className: "bg-sky text-white" },
];

export function ReviewPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<DailyBatch>({
    queryKey: ["review-batch"],
    queryFn: (): Promise<DailyBatch> => fetchApi<DailyBatch>("/api/review/batch"),
  });

  const { phase, cards, activeIndex, loadCards, reveal, nextCard } =
    useReviewSession();

  // ponytail: one rating_id per submit; server idempotency keys on it. A new id
  // per retry is safe because a failed apply persists nothing.
  const rateMutation = useMutation<SyncResult, Error, { card_id: string; grade: number }>(
    {
      mutationFn: ({ card_id, grade }) =>
        fetchApi<SyncResult>("/api/review/ratings", {
          method: "POST",
          body: JSON.stringify({
            ratings: [
              {
                rating_id: crypto.randomUUID(),
                card_id,
                grade,
                rated_at: new Date().toISOString(),
              },
            ],
          }),
        }),
      onSuccess: () => {
        // Only advance once the rating is persisted. Refresh the dashboard count.
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
        nextCard();
      },
    },
  );

  useEffect(() => {
    if (data?.cards) {
      loadCards(data.cards);
    }
  }, [data, loadCards]);

  if (isLoading) return <ReviewSkeleton />;
  if (error) return <div className="p-8 text-berry">Failed to load review batch</div>;

  if (cards.length === 0) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-8 text-center">
        <h1 className="text-3xl font-display font-bold text-ink mb-4">Review</h1>
        <p className="text-ink-mute text-lg">No more cards to review today.</p>
      </main>
    );
  }

  const card = cards[activeIndex];
  if (!card) return null;

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-display font-bold text-ink">Review</h1>
        <span className="text-sm text-ink-mute">
          {activeIndex + 1} / {cards.length}
        </span>
      </div>

      <div className="bg-white border-2 border-cream-300 rounded-2xl p-8 shadow-pop-sm min-h-[240px] flex flex-col items-center justify-center">
        <div className="text-4xl font-display font-bold text-ink mb-2">
          {card.token}
        </div>

        {phase === "revealed" && (
          <div className="w-full text-center space-y-4 mt-4 animate-pop-in">
            <p className="text-lg text-ink-soft">{card.definition}</p>
            {card.example_sentence && (
              <p className="text-sm text-ink-mute italic">
                "{card.example_sentence}"
              </p>
            )}
            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {RATINGS.map((r) => (
                <button
                  key={r.grade}
                  onClick={() =>
                    rateMutation.mutate({ card_id: card.review_id, grade: r.grade })
                  }
                  disabled={rateMutation.isPending}
                  className={`px-4 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 ${r.className}`}
                >
                  {r.label}
                </button>
              ))}
            </div>
            {rateMutation.isError && (
              <p className="mt-4 text-sm text-berry">
                Couldn't save your rating — check your connection and try again.
              </p>
            )}
          </div>
        )}

        {phase === "showing" && (
          <button
            onClick={reveal}
            className="mt-6 px-6 py-3 bg-tangerine text-white font-medium rounded-xl hover:bg-tangerine-dark transition-colors"
          >
            Show Answer
          </button>
        )}
      </div>
    </main>
  );
}

function ReviewSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="h-8 bg-cream-200 rounded w-32 mb-6" />
      <div className="bg-cream-200 rounded-2xl p-8 min-h-[240px]" />
    </main>
  );
}
