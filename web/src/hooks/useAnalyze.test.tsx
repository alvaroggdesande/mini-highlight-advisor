import { it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useAnalyze } from "./useAnalyze";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";

const photo = { photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1], material: "matte" } };
beforeEach(() => { vi.restoreAllMocks(); useProjectStore.setState(useProjectStore.getInitialState(), true); });

it("sets analyzing during the request and clears it after", async () => {
  let resolve!: (v: any) => void;
  vi.spyOn(client, "analyze").mockReturnValue(new Promise((r) => { resolve = r; }));
  useProjectStore.getState().initFromPhoto(photo as any);
  renderHook(() => useAnalyze(0));
  await waitFor(() => expect(useProjectStore.getState().angles[0].analyzing).toBe(true));
  resolve({ preview_png: "data:x", result_token: "t" });
  await waitFor(() => expect(useProjectStore.getState().angles[0].analyzing).toBe(false));
});

it("invalid hex never sets analyzing", async () => {
  const spy = vi.spyOn(client, "analyze");
  useProjectStore.getState().initFromPhoto(photo as any);
  useProjectStore.getState().setPaletteAt(0, [{ name: "a", hex: "#zz" }]);
  renderHook(() => useAnalyze(0));
  await new Promise((r) => setTimeout(r, 20));
  expect(spy).not.toHaveBeenCalled();
  expect(useProjectStore.getState().angles[0].analyzing).toBeFalsy();
});

it("retryAnalyze re-runs analyze", async () => {
  const spy = vi.spyOn(client, "analyze").mockRejectedValueOnce(new Error("500"))
    .mockResolvedValue({ preview_png: "data:x", result_token: "t" } as any);
  useProjectStore.getState().initFromPhoto(photo as any);
  renderHook(() => useAnalyze(0));
  await waitFor(() => expect(useProjectStore.getState().angles[0].error).toBe("500"));
  useProjectStore.getState().retryAnalyze();
  await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
});

it("an older response neither clears analyzing nor overwrites the newer preview", async () => {
  const resolvers: Array<(v: any) => void> = [];
  vi.spyOn(client, "analyze").mockImplementation(() => new Promise((r) => { resolvers.push(r); }));
  useProjectStore.getState().initFromPhoto(photo as any);
  renderHook(() => useAnalyze(0));
  await waitFor(() => expect(resolvers).toHaveLength(1));
  useProjectStore.getState().setPaletteAt(0, [{ name: "b", hex: "#111111" }]);   // edit → request B
  await waitFor(() => expect(resolvers).toHaveLength(2));
  resolvers[1]({ preview_png: "data:B", result_token: "tB" });
  await waitFor(() => expect(useProjectStore.getState().angles[0].preview).toBe("data:B"));
  resolvers[0]({ preview_png: "data:A", result_token: "tA" });
  await new Promise((r) => setTimeout(r, 10));
  expect(useProjectStore.getState().angles[0].preview).toBe("data:B");
  expect(useProjectStore.getState().angles[0].analyzing).toBe(false);
});

it("an older response finishing first neither clears analyzing nor sets the preview", async () => {
  const resolvers: Array<(v: any) => void> = [];
  vi.spyOn(client, "analyze").mockImplementation(() => new Promise((r) => { resolvers.push(r); }));
  useProjectStore.getState().initFromPhoto(photo as any);
  renderHook(() => useAnalyze(0));
  await waitFor(() => expect(resolvers).toHaveLength(1));
  useProjectStore.getState().setPaletteAt(0, [{ name: "b", hex: "#111111" }]);
  await waitFor(() => expect(resolvers).toHaveLength(2));
  resolvers[0]({ preview_png: "data:A", result_token: "tA" });   // older finishes first
  await new Promise((r) => setTimeout(r, 10));
  expect(useProjectStore.getState().angles[0].analyzing).toBe(true);
  expect(useProjectStore.getState().angles[0].preview).toBeUndefined();
});

it("switching angle mid-request does not leak the result or leave the old angle analyzing", async () => {
  const resolvers: Array<(v: any) => void> = [];
  vi.spyOn(client, "analyze").mockImplementation(() => new Promise((r) => { resolvers.push(r); }));
  useProjectStore.getState().initFromPhoto(photo as any);
  renderHook(() => useAnalyze(0));
  await waitFor(() => expect(resolvers).toHaveLength(1));
  act(() => useProjectStore.getState().addAngle({ ...photo, photo_id: "p2" } as any));   // active → 1
  await waitFor(() => expect(resolvers).toHaveLength(2));
  resolvers[0]({ preview_png: "data:A0", result_token: "t0" });
  await new Promise((r) => setTimeout(r, 10));
  const [a0, a1] = useProjectStore.getState().angles;
  expect(a1.preview).toBeUndefined();
  expect(a0.analyzing).toBe(false);
});
