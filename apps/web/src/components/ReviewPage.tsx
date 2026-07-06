import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { fetchApi } from "@/api/client";
import { DoneCard } from "@/components/DoneCard";
import { PronunciationGate } from "@/components/PronunciationGate";
import { Button } from "@/components/ui/Button";
import { Card as Paper } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { RatingButton, type RatingQuality } from "@/components/ui/RatingButton";
import { Washi } from "@/components/ui/Washi";
import { useAudioQueue } from "@/components/useAudioQueue";
import { hasSeen, markSeen, SEEN_KEYS } from "@/lib/seen";
import { useReviewSession, type Card } from "@/store/reviewSession";

interface DailyBatch {
  cards: Card[];
}

export function ReviewPage() {
  const { data, isLoading, error, refetch } = useQuery<DailyBatch>({
    queryKey: ["review-batch"],
    queryFn: (): Promise<DailyBatch> => fetchApi<DailyBatch>("/api/review/batch"),
  });
  const {
    phase,
    cards,
    activeIndex,
    sessionCount,
    completed,
    loadCards,
    reveal,
    allowRating,
    nextCard,
    enqueueRating,
  } = useReviewSession();
  const { audioRef, play, stop } = useAudioQueue();
  const [playing, setPlaying] = useState(false);
  const [showRatingHint, setShowRatingHint] = useState(
    () => !hasSeen(SEEN_KEYS.rating),
  );

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onPlay = () => setPlaying(true);
    const onStop = () => setPlaying(false);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onStop);
    audio.addEventListener("ended", onStop);
    return () => {
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onStop);
      audio.removeEventListener("ended", onStop);
    };
  }, [audioRef]);

  useEffect(() => {
    if (data?.cards) loadCards(data.cards);
  }, [data, loadCards]);

  useEffect(() => {
    if (phase !== "gated") return;
    const card = cards[activeIndex];
    if (card) play([card.word_audio_url || "", card.example_audio_url || ""]);
  }, [activeIndex, cards, phase, play]);

  const handleRate = useCallback(
    (grade: RatingQuality) => {
      const card = cards[activeIndex];
      if (!card || phase !== "ratable") return;
      markSeen(SEEN_KEYS.rating);
      setShowRatingHint(false);
      enqueueRating({
        rating_id: crypto.randomUUID(),
        card_id: card.review_id,
        grade,
        rated_at: new Date().toISOString(),
      });
      nextCard();
    },
    [activeIndex, cards, enqueueRating, nextCard, phase],
  );

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (
        event.key === " " &&
        phase === "showing" &&
        !(event.target instanceof HTMLButtonElement)
      ) {
        event.preventDefault();
        reveal();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [phase, reveal]);

  if (isLoading) return <ReviewSkeleton />;

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Paper
          role="alert"
          tilt="l"
          className="text-center text-ink"
          washi={<Washi color="berry" className="-top-3 -left-3 tilt-l" />}
        >
          <p className="text-lg font-semibold">Your words did not load.</p>
          <Button variant="berry" className="mt-4" onClick={() => void refetch()}>
            Try again
          </Button>
        </Paper>
      </main>
    );
  }

  if (cards.length === 0) {
    if (completed) {
      return (
        <main className="mx-auto max-w-2xl px-4 py-8">
          <DoneCard count={sessionCount} />
        </main>
      );
    }
    return (
      <main className="mx-auto max-w-2xl px-4 py-8 text-center">
        <h1 className="mb-4 font-display text-3xl font-black text-ink">
          Practice
        </h1>
        <Paper size="lg" animate="pop-in" tilt="r">
          <h2 className="font-display text-3xl font-black text-ink">
            No words today!
          </h2>
          <p className="mt-2 text-lg text-ink-soft">Come back tomorrow.</p>
          <p className="mt-6 text-ink-soft">Want more? Add a new word!</p>
          <Link
            to="/dashboard"
            className="btn-pop btn-pop--primary mt-3 text-base"
          >
            Add a new word
          </Link>
        </Paper>
      </main>
    );
  }

  const card = cards[activeIndex];
  if (!card) return null;

  const isPrompt = phase === "showing";
  const isRevealed = phase === "gated" || phase === "ratable";
  const isRatable = phase === "ratable";
  const hasReferenceAudio = Boolean(
    card.word_audio_url || card.example_audio_url,
  );

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <audio ref={audioRef} className="hidden" />
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-black text-ink">Practice</h1>
          <Chip dotColor="bg-tangerine">
            {activeIndex + 1} / {cards.length}
          </Chip>
        </div>
      </div>

      {isPrompt && (
        <button
          type="button"
          aria-label="Show the meaning"
          onClick={reveal}
          className="card-paper--lg perspective-card relative min-h-[240px] w-full tilt-l-2 animate-pop-in flex flex-col items-center justify-center text-center focus-visible:ring-4 focus-visible:ring-tangerine/30"
        >
          <Washi color="honey" className="-top-3 -left-3 tilt-l" />
          <span className="mb-2 font-display text-4xl font-black text-ink">
            {card.token}
          </span>
          <span className="text-base text-ink-soft">Tap to see!</span>
        </button>
      )}

      {isRevealed && (
        <Paper
          size="lg"
          tilt="r"
          animate="flip-in"
          washi={<Washi color="teal" className="-top-3 -right-3 tilt-r" />}
          className="flex min-h-[240px] flex-col items-center justify-center text-center"
        >
          <div className="mb-2 flex items-center gap-2 font-display text-3xl font-black text-ink">
            {card.token}
            {hasReferenceAudio && (
              <button
                type="button"
                onClick={() => {
                  if (playing) stop();
                  else play([card.word_audio_url || "", card.example_audio_url || ""]);
                }}
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border-2 border-ink text-sm hover:bg-cream-100"
                aria-label={playing ? "Stop the sound" : "Hear it again"}
              >
                {playing ? "⏹" : "🔊"}
              </button>
            )}
          </div>
          <p className="mb-4 text-lg text-ink-soft">{card.definition}</p>
          {card.example_sentence && (
            <div className="mb-6 rounded-xl border-2 border-dashed border-ink/20 px-4 py-3">
              <p className="text-sm italic text-ink-mute">
                &quot;{card.example_sentence}&quot;
              </p>
            </div>
          )}

          <PronunciationGate
            key={card.review_id}
            vocabItemId={card.vocab_item_id}
            hasReferenceAudio={hasReferenceAudio}
            onDone={allowRating}
          />

          <div className="mt-6 min-h-[152px] w-full">
            {isRatable && (
              <div className="animate-rise">
                {showRatingHint && (
                  <p className="mb-3 text-base text-ink-soft">
                    How well did you know it? Pick a face!
                  </p>
                )}
                <div className="grid w-full grid-cols-2 gap-3 sm:grid-cols-4">
                  <RatingButton quality={0} onClick={() => handleRate(0)} />
                  <RatingButton quality={2} onClick={() => handleRate(2)} />
                  <RatingButton quality={4} onClick={() => handleRate(4)} />
                  <RatingButton quality={5} onClick={() => handleRate(5)} />
                </div>
              </div>
            )}
          </div>
        </Paper>
      )}
    </main>
  );
}

function ReviewSkeleton() {
  return (
    <main className="mx-auto max-w-2xl animate-pulse px-4 py-8">
      <div className="mb-6 h-8 w-32 rounded bg-cream-200" />
      <div className="min-h-[240px] rounded-[28px] bg-cream-200 p-8" />
    </main>
  );
}
