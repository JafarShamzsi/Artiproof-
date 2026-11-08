import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "@/lib/api";
import { analysisIsActive, useAnalysisRefresh } from "./use-analysis-refresh";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
const fetchMock = vi.mocked(apiFetch);
const response = (status: number, data = {}) => ({ ok: status === 200, status, json: async () => data }) as Response;
const tick = (ms = 3000) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

beforeEach(() => { vi.useFakeTimers(); fetchMock.mockReset(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("running analysis refresh", () => {
  it("refreshes running data and stops at completion or failure", async () => {
    const update = vi.fn();
    fetchMock.mockResolvedValue(response(200, { status: "processing" }));
    const { rerender } = renderHook(({ status }) => useAnalysisRefresh("/result", analysisIsActive(status), update),
      { initialProps: { status: "pending" } });
    await tick();
    expect(update).toHaveBeenCalledWith({ status: "processing" }, expect.any(AbortSignal));
    rerender({ status: "completed" });
    await tick(9000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    rerender({ status: "processing" });
    await tick();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    rerender({ status: "failed" });
    await tick(9000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retains the last result through network and server failures, then recovers", async () => {
    const update = vi.fn();
    fetchMock.mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(response(503)).mockResolvedValueOnce(response(200, { status: "completed" }));
    const { result } = renderHook(() => useAnalysisRefresh("/result", true, update));
    await tick();
    expect(result.current).toContain("Retrying automatically");
    await tick();
    expect(update).not.toHaveBeenCalled();
    await tick();
    expect(result.current).toBeNull();
    expect(update).toHaveBeenCalledOnce();
  });

  it.each([401, 403, 404])("stops automatic requests after HTTP %s", async (status) => {
    const update = vi.fn();
    fetchMock.mockResolvedValue(response(status));
    const { result } = renderHook(() => useAnalysisRefresh("/result", true, update));
    await tick(15000);
    expect(result.current).toContain("check your access");
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(update).not.toHaveBeenCalled();
  });

  it("does not overlap slow requests or apply a response after navigation", async () => {
    let resolve!: (value: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
    const update = vi.fn();
    const { rerender, unmount } = renderHook(({ url }) => useAnalysisRefresh(url, true, update),
      { initialProps: { url: "/first" } });
    await tick(12000);
    expect(fetchMock).toHaveBeenCalledOnce();
    const signal = fetchMock.mock.calls[0][1]?.signal;
    rerender({ url: "/second" });
    expect(signal?.aborted).toBe(true);
    await act(async () => resolve(response(200, { id: "first" })));
    expect(update).not.toHaveBeenCalled();
    unmount();
    await tick();
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
