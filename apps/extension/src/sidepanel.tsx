import { useEffect, useRef, useCallback, useState } from "react";
import { createRoot } from "react-dom/client";
import { fetchApi } from "./api/client";
import { useReviewSession, type Card } from "./store/review";

interface DailyBatch {
  cards: Card[];
}

function useAudio() {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const play = useCallback((urls: string[]) => {
    const valid = urls.filter((u) => u);
    if (valid.length === 0) return;
    const a = audioRef.current;
    if (!a) return;

    a.src = valid[0];
    a.play().catch(() => {});

    let idx = 0;
    a.onended = () => {
      idx++;
      if (idx < valid.length) {
        a.src = valid[idx];
        a.play().catch(() => {});
      }
    };
  }, []);

  const stop = useCallback(() => {
    const a = audioRef.current;
    if (a) {
      a.pause();
      a.currentTime = 0;
    }
  }, []);

  return { audioRef, play, stop };
}

function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { phase, cards, activeIndex, loadCards, reveal, nextCard } =
    useReviewSession();
  const { audioRef, play, stop } = useAudio();

  useEffect(() => {
    fetchApi<DailyBatch>("/api/review/batch")
      .then((data) => {
        if (data.cards.length === 0) {
          useReviewSession.getState().loadCards([]);
          useReviewSession.setState({ phase: "done" });
        } else {
          loadCards(data.cards);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [loadCards]);

  useEffect(() => {
    if (phase === "revealed") {
      const c = cards[activeIndex];
      if (c) {
        play([c.word_audio_url || "", c.example_audio_url || ""]);
      }
    }
  }, [phase, activeIndex, cards, play]);

  const handleReveal = () => {
    stop();
    reveal();
  };

  const handleRate = (quality: number) => {
    stop();
    const c = cards[activeIndex];
    if (!c) return;
    fetchApi("/api/review/ratings", {
      method: "POST",
      body: JSON.stringify({
        ratings: [
          {
            rating_id: crypto.randomUUID(),
            card_id: c.review_id,
            grade: quality,
            rated_at: new Date().toISOString(),
          },
        ],
      }),
    }).catch(() => {});
    nextCard();
  };

  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === " ") {
        e.preventDefault();
        if (phase === "showing") {
          handleReveal();
        }
      }
    },
    [phase],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  if (loading) {
    return <div className="p-4 text-sm text-slate-500">Loading...</div>;
  }

  if (error) {
    return <div className="p-4 text-sm text-red-500">{error}</div>;
  }

  if (phase === "done") {
    return (
      <div className="flex flex-col items-center gap-3 p-6 text-center">
        <div className="text-lg font-bold">All caught up</div>
        <div className="text-sm text-slate-500">
          No more cards to review today.
        </div>
      </div>
    );
  }

  const card = cards[activeIndex];
  if (!card) return null;

  return (
    <div className="flex flex-col gap-3 p-4 min-h-[300px]">
      <audio ref={audioRef} className="hidden" />

      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>Review</span>
        <span>{activeIndex + 1}/{cards.length}</span>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
        <div className="text-2xl font-bold">{card.token}</div>

        {phase === "showing" && (
          <button
            onClick={handleReveal}
            className="mt-3 px-6 py-2 bg-blue-600 text-white rounded-xl text-sm"
          >
            Show Answer
          </button>
        )}

        {phase === "revealed" && (
          <>
            <div className="text-sm text-slate-600">{card.definition}</div>
            {card.example_sentence && (
              <div className="text-xs text-slate-400 italic">
                "{card.example_sentence}"
              </div>
            )}
          </>
        )}
      </div>

      {phase === "revealed" && (
        <div className="grid grid-cols-4 gap-1.5">
          <RatingBtn
            emoji="😢"
            label="Again"
            color="#e63946"
            onClick={() => handleRate(0)}
          />
          <RatingBtn
            emoji="🤔"
            label="Hard"
            color="#ffb627"
            onClick={() => handleRate(2)}
          />
          <RatingBtn
            emoji="😊"
            label="Good"
            color="#06a77d"
            onClick={() => handleRate(4)}
          />
          <RatingBtn
            emoji="🔥"
            label="Easy"
            color="#3a86ff"
            onClick={() => handleRate(5)}
          />
        </div>
      )}
    </div>
  );
}

function RatingBtn({
  emoji,
  label,
  color,
  onClick,
}: {
  emoji: string;
  label: string;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-0.5 py-2 rounded-xl border-2 border-slate-800 text-xs font-bold hover:-translate-y-0.5 transition-transform"
      style={{ backgroundColor: color, color: color === "#ffb627" ? "#1a1a2e" : "#fff" }}
    >
      <span className="text-lg">{emoji}</span>
      <span className="text-[10px] uppercase tracking-wider">{label}</span>
    </button>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
