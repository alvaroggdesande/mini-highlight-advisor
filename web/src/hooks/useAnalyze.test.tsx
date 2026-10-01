import { it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
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
