import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PronunciationGate } from "@/components/PronunciationGate";

const recorder = vi.hoisted(() => ({
  state: "idle",
  blob: null as Blob | null,
  supported: true,
  remainingSeconds: 4,
  start: vi.fn(),
  stop: vi.fn(),
  reset: vi.fn(),
}));

vi.mock("@/hooks/useVoiceRecorder", () => ({
  useVoiceRecorder: () => recorder,
}));

beforeEach(() => {
  localStorage.clear();
  recorder.state = "idle";
  recorder.blob = null;
  recorder.start.mockReset();
  recorder.stop.mockReset();
  recorder.reset.mockReset();
  vi.unstubAllGlobals();
});

describe("PronunciationGate", () => {
  it("shows the mic pre-prompt only once", async () => {
    const onDone = vi.fn();
    const first = render(
      <PronunciationGate
        vocabItemId="v1"
        hasReferenceAudio
        onDone={onDone}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "🎤 Say the word!" }));
    expect(await screen.findByText("We want to hear you!")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    first.unmount();

    render(
      <PronunciationGate
        vocabItemId="v2"
        hasReferenceAudio
        onDone={onDone}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "🎤 Say the word!" }));
    await waitFor(() => expect(recorder.start).toHaveBeenCalledOnce());
    expect(screen.queryByText("We want to hear you!")).not.toBeInTheDocument();
  });

  it("keeps the rating path reachable after mic denial", () => {
    recorder.state = "denied";
    const onDone = vi.fn();
    render(
      <PronunciationGate
        vocabItemId="v1"
        hasReferenceAudio
        onDone={onDone}
      />,
    );

    expect(screen.getByText("That's okay!")).toBeInTheDocument();
    expect(screen.getByText("We can't hear you this time.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep going" }));
    expect(onDone).toHaveBeenCalledOnce();
  });

  it.each([
    [true, 0.9, "✅ You said it!"],
    [false, 0.2, "🔁 Almost! Try again or pick a face."],
  ] as const)("renders the fixed verdict copy", async (saidTarget, confidence, copy) => {
    recorder.state = "ready";
    recorder.blob = new Blob(["audio"], { type: "audio/webm" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            said_target: saidTarget,
            confidence,
            feedback: "Dynamic LLM feedback",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    render(
      <PronunciationGate
        vocabItemId="v1"
        hasReferenceAudio
        onDone={vi.fn()}
      />,
    );

    expect(await screen.findByText(copy)).toBeInTheDocument();
    expect(screen.queryByText("Dynamic LLM feedback")).not.toBeInTheDocument();
  });

  it("shows the unsupported fallback with a way forward", async () => {
    recorder.state = "unsupported";
    const onDone = vi.fn();
    render(
      <PronunciationGate
        vocabItemId="v1"
        hasReferenceAudio
        onDone={onDone}
      />,
    );

    expect(
      screen.getByText("We can't hear you here. Say the word out loud!"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep going" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledOnce());
  });
});
