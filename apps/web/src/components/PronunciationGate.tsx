import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { hasSeen, markSeen, SEEN_KEYS } from "@/lib/seen";

interface PronunciationVerdict {
  said_target: boolean;
  confidence: number;
}

function isPronunciationVerdict(value: unknown): value is PronunciationVerdict {
  return (
    typeof value === "object" &&
    value !== null &&
    "said_target" in value &&
    "confidence" in value &&
    typeof value.said_target === "boolean" &&
    typeof value.confidence === "number"
  );
}

export function PronunciationGate({
  vocabItemId,
  hasReferenceAudio,
  onDone,
}: {
  vocabItemId: string;
  hasReferenceAudio: boolean;
  onDone: () => void;
}) {
  const [checking, setChecking] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [error, setError] = useState(false);
  const [verdict, setVerdict] = useState<PronunciationVerdict | null>(null);
  const recorder = useVoiceRecorder();
  const micWasDenied = hasSeen(SEEN_KEYS.micDenied);

  useEffect(() => {
    setVerdict(null);
    setError(false);
    setShowPrompt(false);
  }, [vocabItemId]);

  useEffect(() => {
    if (!hasReferenceAudio || micWasDenied) onDone();
  }, [hasReferenceAudio, micWasDenied, onDone]);

  useEffect(() => {
    if (recorder.state === "denied") markSeen(SEEN_KEYS.micDenied);
  }, [recorder.state]);

  useEffect(() => {
    if (verdict?.said_target && verdict.confidence >= 0.6) {
      const timer = setTimeout(onDone, 1200);
      return () => clearTimeout(timer);
    }
  }, [onDone, verdict]);

  const startRecording = async () => {
    if (!hasSeen(SEEN_KEYS.mic)) {
      try {
        const permission = await navigator.permissions?.query({
          name: "microphone" as PermissionName,
        });
        if (!permission || permission.state === "prompt") {
          setShowPrompt(true);
          return;
        }
      } catch {
        setShowPrompt(true);
        return;
      }
      markSeen(SEEN_KEYS.mic);
    }
    await recorder.start();
  };

  const handleSubmit = async () => {
    if (!recorder.blob) return;
    setChecking(true);
    try {
      const form = new FormData();
      form.append("audio", recorder.blob, "recording.webm");
      form.append("vocab_item_id", vocabItemId);
      const response = await fetch(
        `/api/review/pronunciation?vocab_item_id=${encodeURIComponent(vocabItemId)}`,
        { method: "POST", body: form, credentials: "include" },
      );
      if (response.status === 503) {
        onDone();
        return;
      }
      if (!response.ok) throw new Error("Pronunciation request failed");
      const data: unknown = await response.json();
      if (!isPronunciationVerdict(data)) throw new Error("Invalid response");
      setError(false);
      setVerdict(data);
    } catch {
      setError(true);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    if (recorder.state === "ready" && recorder.blob && !checking && !verdict) {
      void handleSubmit();
    }
  }, [recorder.state, recorder.blob]);

  if (!hasReferenceAudio) return null;

  const retry = () => {
    recorder.reset();
    setVerdict(null);
    setError(false);
  };

  if (micWasDenied && recorder.state !== "denied") {
    return (
      <div className="mt-4" aria-live="polite">
        <span className="inline-flex min-h-11 items-center rounded-full border-2 border-ink bg-berry-light px-4 text-sm font-bold text-ink">
          🎤 off — say it out loud!
        </span>
      </div>
    );
  }

  if (showPrompt) {
    return (
      <div
        className="card-paper mt-4 border-2 border-ink bg-honey-light text-left"
        aria-live="polite"
      >
        <h2 className="font-display text-2xl font-black text-ink">
          We want to hear you!
        </h2>
        <p className="mt-2 text-ink-soft">Your tablet will ask a question.</p>
        <p className="text-ink-soft">Tap &quot;Allow&quot;. Then we can hear you!</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button
            variant="honey"
            onClick={() => {
              markSeen(SEEN_KEYS.mic);
              setShowPrompt(false);
              void recorder.start();
            }}
          >
            Let&apos;s go!
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              markSeen(SEEN_KEYS.mic);
              onDone();
            }}
          >
            Not now
          </Button>
        </div>
      </div>
    );
  }

  if (recorder.state === "denied") {
    return (
      <div
        className="card-paper mt-4 border-2 border-ink bg-berry-light"
        aria-live="polite"
      >
        <h2 className="font-display text-2xl font-black text-ink">
          That&apos;s okay!
        </h2>
        <p className="mt-2 text-ink-soft">We can&apos;t hear you this time.</p>
        <p className="text-ink-soft">
          Say the word out loud. Then pick a face!
        </p>
        <Button variant="berry" className="mt-4" onClick={onDone}>
          Keep going
        </Button>
      </div>
    );
  }

  if (recorder.state === "unsupported") {
    return (
      <div className="card-paper mt-4" aria-live="polite">
        <p className="text-ink-soft">
          We can&apos;t hear you here. Say the word out loud!
        </p>
        <Button variant="ghost" className="mt-4" onClick={onDone}>
          Keep going
        </Button>
      </div>
    );
  }

  const succeeded = verdict?.said_target && verdict.confidence >= 0.6;

  return (
    <div className="mt-4 space-y-3 text-center" aria-live="polite">
      {error && (
        <p className="text-sm font-medium text-honey-dark">
          We could not hear you. Try again!
        </p>
      )}

      {succeeded && (
        <p className="text-sm font-bold text-teal">✅ You said it!</p>
      )}

      {verdict && !succeeded && (
        <p className="text-sm font-bold text-berry">
          🔁 Almost! Try again or pick a face.
        </p>
      )}

      {recorder.state === "idle" && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button variant="primary" onClick={() => void startRecording()}>
            🎤 Say the word!
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Skip
          </Button>
        </div>
      )}

      {recorder.state === "recording" && (
        <div className="space-y-3">
          <p className="font-medium text-berry">🎤 We are listening!</p>
          <progress
            aria-label={`${recorder.remainingSeconds} seconds left`}
            className="h-3 w-full accent-berry"
            max={4}
            value={recorder.remainingSeconds}
          />
          <p className="text-sm text-ink-soft">{recorder.remainingSeconds}s</p>
          <Button variant="ghost" onClick={recorder.stop}>
            I said it!
          </Button>
        </div>
      )}

      {recorder.state === "ready" && !checking && !verdict && !error && (
        <p className="text-sm text-ink-soft">Checking your word…</p>
      )}

      {(error || (verdict && !succeeded)) && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button variant="ghost" onClick={retry}>
            Try again
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Skip
          </Button>
        </div>
      )}

      {checking && (
        <div className="space-y-3">
          <p className="text-sm text-ink-soft">Checking your word…</p>
          <Button variant="ghost" onClick={onDone}>
            Skip
          </Button>
        </div>
      )}
    </div>
  );
}
