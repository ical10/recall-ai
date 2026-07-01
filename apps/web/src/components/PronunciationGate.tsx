import { useState, useEffect } from "react";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { Button } from "@/components/ui/Button";

interface PronunciationVerdict {
  said_target: boolean;
  heard: string;
  confidence: number;
  feedback: string;
}

export function PronunciationGate({
  vocabItemId,
  onDone,
}: {
  vocabItemId: string;
  onDone: () => void;
}) {
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<PronunciationVerdict | null>(null);
  const recorder = useVoiceRecorder();

  if (!recorder.supported) {
    return (
      <div className="text-center mt-4">
        <Button variant="ghost" onClick={onDone}>
          Skip
        </Button>
      </div>
    );
  }

  const handleSubmit = async () => {
    if (!recorder.blob) return;
    setChecking(true);
    try {
      const form = new FormData();
      form.append("audio", recorder.blob, "recording.webm");
      form.append("vocab_item_id", vocabItemId);
      const resp = await fetch(
        `/api/review/pronunciation?vocab_item_id=${encodeURIComponent(vocabItemId)}`,
        {
          method: "POST",
          body: form,
          credentials: "include",
        }
      );
      if (!resp.ok) {
        if (resp.status === 503) {
          onDone();
          return;
        }
        setError("Hmm, couldn't check that — try again");
        return;
      }
      setError(null);
      const data: PronunciationVerdict = await resp.json();
      setVerdict(data);
      if (data.said_target && data.confidence >= 0.6) {
        setTimeout(onDone, 1500);
      }
    } catch {
      // fail-open: allow skip
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    if (
      recorder.state === "ready" &&
      recorder.blob &&
      !checking &&
      !verdict
    ) {
      handleSubmit();
    }
  }, [recorder.state, recorder.blob]); // eslint-disable-line react-hooks/exhaustive-deps

  if (verdict && verdict.said_target && verdict.confidence >= 0.6) {
    return (
      <div className="text-center mt-4 text-teal text-sm font-medium">
        ✅ {verdict.feedback}
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3 text-center">
      {error && (
        <div className="text-amber-600 text-sm mb-2">{error}</div>
      )}

      {verdict && !verdict.said_target && (
        <div className="text-berry text-sm mb-2">🔁 {verdict.feedback}</div>
      )}

      {recorder.state === "idle" && (
        <div className="flex items-center justify-center gap-3">
          <Button variant="primary" onClick={recorder.start}>
            🎤 Say it
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Skip
          </Button>
        </div>
      )}

      {recorder.state === "recording" && (
        <div className="space-y-2">
          <div className="text-sm animate-pulse text-berry">🎤 Recording...</div>
          <Button variant="ghost" onClick={recorder.stop}>
            Stop
          </Button>
        </div>
      )}

      {recorder.state === "ready" && !checking && (
        <div className="flex items-center justify-center gap-3">
          <Button variant="ghost" onClick={() => { recorder.reset(); setVerdict(null); setError(null); }}>
            🔁 Retry
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Skip
          </Button>
        </div>
      )}

      {checking && (
        <div className="text-sm animate-pulse text-ink-mute">Checking pronunciation...</div>
      )}
    </div>
  );
}
