import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useVoiceRecorder", () => {
  it("reports unsupported when media devices are unavailable", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    });
    const { result } = renderHook(() => useVoiceRecorder());

    await act(() => result.current.start());
    expect(result.current.state).toBe("unsupported");
  });

  it("reports denied for NotAllowedError", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(new DOMException("Permission denied", "NotAllowedError")),
      },
    });
    const { result } = renderHook(() => useVoiceRecorder());

    await act(() => result.current.start());
    await waitFor(() => expect(result.current.state).toBe("denied"));
  });
});
