import { useEffect, useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";
import { useReviewSession, type Card } from "@/store/reviewSession";
import { Card as Paper } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { RatingButton } from "@/components/ui/RatingButton";
import { Washi } from "@/components/ui/Washi";
import { Chip } from "@/components/ui/Chip";
import { DoneCard } from "@/components/DoneCard";
import { useAudioQueue } from "@/components/useAudioQueue";
import { PronunciationGate } from "@/components/PronunciationGate";

interface DailyBatch {
  cards: Card[];
}

export function ReviewPage() {
  const { data, isLoading, error } = useQuery<DailyBatch>({
    queryKey: ["review-batch"],
    queryFn: (): Promise<DailyBatch> => fetchApi<DailyBatch>("/api/review/batch"),
  });

  const { phase, cards, activeIndex, completed, loadCards, reveal, nextCard } =
    useReviewSession();

  const { audioRef, play, stop } = useAudioQueue();
  const [playing, setPlaying] = useState(false);
  const [pronunciationDone, setPronunciationDone] = useState(false);

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onPlay = () => setPlaying(true);
    const onEnded = () => setPlaying(false);
    a.addEventListener("play", onPlay);
    a.addEventListener("ended", onEnded);
    return () => {
      a.removeEventListener("play", onPlay);
      a.removeEventListener("ended", onEnded);
    };
  }, []);

  useEffect(() => {
    if (data?.cards) {
      loadCards(data.cards);
    }
  }, [data, loadCards]);

  useEffect(() => {
    if (phase === "revealed") {
      const c = cards[activeIndex];
      if (c) {
        play([c.word_audio_url || "", c.example_audio_url || ""]);
      }
    }
  }, [phase, activeIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRate = useCallback(
    (quality: number) => {
      const c = cards[activeIndex];
      if (!c) return;
      const ratingId = crypto.randomUUID();
      fetchApi("/api/review/ratings", {
        method: "POST",
        body: JSON.stringify({
          ratings: [
            {
              rating_id: ratingId,
              card_id: c.review_id,
              grade: quality,
              rated_at: new Date().toISOString(),
            },
          ],
        }),
      }).catch(() => {});
      nextCard();
    },
    [cards, activeIndex, nextCard],
  );

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === " " && phase === "showing") {
        e.preventDefault();
        reveal();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [phase, reveal]);

  if (isLoading) return <ReviewSkeleton />;
  if (error) return <div className="p-8 text-berry">Failed to load review batch</div>;

  if (cards.length === 0) {
    if (completed) {
      return (
        <main className="max-w-2xl mx-auto px-4 py-8">
          <DoneCard />
        </main>
      );
    }
    return (
      <main className="max-w-2xl mx-auto px-4 py-8 text-center">
        <h1 className="text-3xl font-display font-black text-ink mb-4">Review</h1>
        <Paper size="lg" animate="pop-in">
          <p className="text-ink-mute text-lg">No cards due for review.</p>
        </Paper>
      </main>
    );
  }

  const card = cards[activeIndex];
  if (!card) return null;

  const isPromp = phase === "showing";
  const isRevealed = phase === "revealed";

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <audio ref={audioRef} className="hidden" />
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-display font-black text-ink">Review</h1>
          <Chip dotColor="bg-tangerine">{activeIndex + 1}/{cards.length}</Chip>
        </div>
      </div>

      {isPromp && (
        <Paper
          size="lg"
          tilt="l-2"
          animate="pop-in"
          washi={<Washi color="honey" className="-top-3 -left-3 tilt-l" />}
          className="perspective-card min-h-[240px] flex flex-col items-center justify-center text-center"
        >
          <div className="text-4xl font-display font-black text-ink mb-2">
            {card.token}
          </div>
          <p className="text-sm text-ink-mute font-mono tracking-wider uppercase mb-6">
            Tap to reveal
          </p>
          <Button variant="primary" onClick={reveal}>
            Show Answer
          </Button>
        </Paper>
      )}

      {isRevealed && (
        <Paper
          size="lg"
          tilt="r"
          animate="flip-in"
          washi={<Washi color="teal" className="-top-3 -right-3 tilt-r" />}
          className="min-h-[240px] flex flex-col items-center justify-center text-center"
        >
          <div className="text-3xl font-display font-black text-ink mb-2 flex items-center gap-2">
            {card.token}
            {(card.word_audio_url || card.example_audio_url) && (
              <button
                onClick={() => {
                  if (playing) stop();
                  else play([card.word_audio_url || "", card.example_audio_url || ""]);
                }}
                className="text-sm px-2 py-1 rounded-lg border-2 border-ink hover:bg-cream-100"
                title={playing ? "Stop" : "Replay"}
              >
                {playing ? "⏹" : "🔊"}
              </button>
            )}
          </div>
          <p className="text-lg text-ink-soft mb-4">{card.definition}</p>
          {card.example_sentence && (
            <div className="border-2 border-dashed border-ink/20 rounded-xl px-4 py-3 mb-6">
              <p className="text-sm text-ink-mute italic">
                "{card.example_sentence}"
              </p>
            </div>
          )}

          <PronunciationGate
            vocabItemId={card.vocab_item_id}
            onDone={() => setPronunciationDone(true)}
          />

          {pronunciationDone && (
            <div className="grid grid-cols-4 gap-3 w-full">
            <RatingButton
              emoji="😢"
              label="Again"
              quality={0}
              color="berry"
              onClick={() => handleRate(0)}
            />
            <RatingButton
              emoji="🤔"
              label="Hard"
              quality={2}
              color="honey"
              onClick={() => handleRate(2)}
            />
            <RatingButton
              emoji="😊"
              label="Good"
              quality={4}
              color="teal"
              onClick={() => handleRate(4)}
            />
            <RatingButton
              emoji="🔥"
              label="Easy"
              quality={5}
              color="sky"
              onClick={() => handleRate(5)}
            />
          </div>
          )}
        </Paper>
      )}
    </main>
  );
}

function ReviewSkeleton() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-8 animate-pulse">
      <div className="h-8 bg-cream-200 rounded w-32 mb-6" />
      <div className="bg-cream-200 rounded-[28px] p-8 min-h-[240px]" />
    </main>
  );
}
