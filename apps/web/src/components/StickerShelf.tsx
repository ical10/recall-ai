import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { FlipSticker } from "@/components/ui/FlipSticker";
import { Washi } from "@/components/ui/Washi";
import { cn } from "@/components/ui/cn";
import { SEEN_KEYS, hasSeen, markSeen } from "@/lib/seen";
import type { VocabItem, VocabListResponse } from "@/api/vocab";

const TINT_CLASSES = [
  "bg-tangerine-light",
  "bg-teal-light",
  "bg-berry-light",
  "bg-honey-light",
  "bg-sky-light",
];

export function StickerShelf({ onEmptyCta }: { onEmptyCta: () => void }) {
  const [flipped, setFlipped] = useState<Record<string, boolean>>({});
  const [hintVisible, setHintVisible] = useState(() => !hasSeen(SEEN_KEYS.flip));
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const playWord = (url: string | null) => {
    if (!url) return;
    audioRef.current?.pause();
    const audio = new Audio(url);
    audioRef.current = audio;
    void audio.play().catch(() => {});
  };

  const { data, isLoading, error, refetch } = useQuery<VocabListResponse>({
    queryKey: ["sticker-shelf"],
    queryFn: (): Promise<VocabListResponse> => fetchApi<VocabListResponse>("/api/shelf"),
  });

  const dismissHint = () => {
    markSeen(SEEN_KEYS.flip);
    setHintVisible(false);
  };

  const toggleFlip = (item: VocabItem) => {
    const opening = !flipped[item.id];
    setFlipped((prev) => ({ ...prev, [item.id]: !prev[item.id] }));
    if (opening) playWord(item.word_audio_url);
    if (hintVisible) dismissHint();
  };

  const handleKeyDown = (item: VocabItem) => (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      toggleFlip(item);
    }
  };

  const heading = (
    <h2 className="font-display text-2xl font-black text-ink mb-4">My sticker shelf</h2>
  );

  if (isLoading) {
    return (
      <section>
        {heading}
        <div className="grid grid-cols-2 gap-4 animate-pulse sm:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-28 rounded-2xl bg-cream-200" />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section>
        {heading}
        <div role="alert" className="tilt-l card-paper text-center">
          <p className="font-display text-xl font-black text-ink">Your words did not load.</p>
          <Button variant="ink" className="mt-4" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      </section>
    );
  }

  if (!data) return null;

  if (data.items.length === 0) {
    return (
      <section>
        {heading}
        <button
          type="button"
          onClick={onEmptyCta}
          className="tilt-l-2 relative w-full rounded-2xl border-2 border-dashed border-ink/40 bg-cream-50 p-8 text-center"
        >
          <Washi color="sky" className="-top-3 left-8 tilt-r-2" />
          <p className="font-display text-xl font-black text-ink">Your shelf is empty.</p>
          <p className="mt-2 text-ink-soft">Add a word. It will live here!</p>
        </button>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-display text-2xl font-black text-ink">My sticker shelf</h2>
      </div>

      {hintVisible && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-full border-2 border-ink bg-cream-50 px-4 py-2">
          <span className="text-sm font-medium text-ink-soft">
            Tap a sticker to see what it means!
          </span>
          <button
            type="button"
            aria-label="Dismiss hint"
            onClick={dismissHint}
            className="shrink-0 text-ink-mute hover:text-ink"
          >
            ✕
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {data.items.map((item, i) => {
          const isFlipped = !!flipped[item.id];
          const tint = TINT_CLASSES[i % TINT_CLASSES.length];
          const tilt = i % 2 === 0 ? "tilt-l" : "tilt-r";

          return (
            <div key={item.id} className={cn("relative", tilt)}>
              <FlipSticker
                word={item.token}
                definition={item.definition}
                flipped={isFlipped}
                tintClass={tint}
                ariaLabel={`Show what ${item.token} means`}
                onToggle={() => toggleFlip(item)}
                onKeyDown={handleKeyDown(item)}
              />
              {isFlipped && item.word_audio_url && (
                <button
                  type="button"
                  onClick={() => playWord(item.word_audio_url)}
                  aria-label={`Hear ${item.token}`}
                  className="absolute -right-2 -top-2 inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border-2 border-ink bg-cream-50 shadow-pop-sm hover:bg-cream-100"
                >
                  🔊
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
