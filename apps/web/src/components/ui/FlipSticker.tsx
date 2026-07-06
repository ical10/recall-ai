import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/components/ui/cn";

interface FlipStickerProps {
  word: string;
  definition: string;
  flipped: boolean;
  tintClass: string;
  ariaLabel: string;
  onToggle: () => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLButtonElement>) => void;
}

export function FlipSticker({
  word,
  definition,
  flipped,
  tintClass,
  ariaLabel,
  onToggle,
  onKeyDown,
}: FlipStickerProps) {
  const shouldReduceMotion = useReducedMotion();

  const faceClasses = cn(
    "absolute inset-0 flex min-h-[120px] w-full flex-col items-center justify-center gap-1 rounded-2xl border-2 border-ink p-4 text-center shadow-pop [backface-visibility:hidden]",
    tintClass,
  );

  return (
    <div className="[perspective:1000px]">
      <motion.button
        type="button"
        onClick={onToggle}
        onKeyDown={onKeyDown}
        aria-label={ariaLabel}
        aria-expanded={flipped}
        whileTap={{ scale: 0.97 }}
        whileHover={{ y: -2 }}
        animate={
          shouldReduceMotion
            ? { rotateY: flipped ? 180 : 0 }
            : { rotateY: flipped ? 180 : 0, scale: [null, 1.12, 1] }
        }
        transition={
          shouldReduceMotion
            ? { duration: 0 }
            : {
                rotateY: { type: "spring", stiffness: 220, damping: 18 },
                scale: { duration: 0.45, times: [0, 0.5, 1], ease: "easeOut" },
              }
        }
        className="relative min-h-[120px] w-full [transform-style:preserve-3d] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-tangerine/30"
      >
        <div className={faceClasses} aria-hidden={flipped}>
          <span className="line-clamp-2 break-words font-display text-xl font-black text-ink">
            {word}
          </span>
        </div>
        <div
          className={faceClasses}
          style={{ transform: "rotateY(180deg)" }}
          aria-hidden={!flipped}
        >
          <span className="line-clamp-3 text-sm font-medium text-ink-soft">
            {definition || "…"}
          </span>
        </div>
      </motion.button>
    </div>
  );
}
