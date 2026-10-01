import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { PhotoUploader } from "./PhotoUploader";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";

beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));
afterEach(() => vi.restoreAllMocks());

it("lists sample photos and seeds the store when one is picked", async () => {
  vi.spyOn(client, "listSamplePhotos").mockResolvedValue([{ id: "necron", name: "Necron" }]);
  vi.spyOn(client, "samplePhotoBlob").mockResolvedValue(new Blob(["x"]));
  vi.spyOn(client, "uploadPhoto").mockResolvedValue({
    photo_id: "s1", width: 10, height: 10, quality_checks: [],
    default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1.0], material: "matte" },
  });
  render(
    <MantineProvider>
      <PhotoUploader />
    </MantineProvider>
  );
  const btn = await screen.findByRole("button", { name: /Necron/ });
  btn.click();
  await waitFor(() => expect(useProjectStore.getState().angles).toHaveLength(1));
});

it("shows a friendly error when the upload fails before any angle exists", async () => {
  vi.spyOn(client, "listSamplePhotos").mockResolvedValue([{ id: "necron", name: "Necron" }]);
  vi.spyOn(client, "samplePhotoBlob").mockResolvedValue(new Blob(["x"]));
  vi.spyOn(client, "uploadPhoto").mockRejectedValue(new Error("413 too big"));
  render(<MantineProvider><PhotoUploader /></MantineProvider>);
  (await screen.findByRole("button", { name: /Necron/ })).click();
  expect(await screen.findByText(/413 too big/)).toBeTruthy();
  expect(useProjectStore.getState().angles).toHaveLength(0);
});

it("clears the file input after picking, so the same file can be re-picked after a failure", async () => {
  vi.spyOn(client, "listSamplePhotos").mockResolvedValue([]);
  vi.spyOn(client, "uploadPhoto").mockRejectedValue(new Error("500"));
  const { container } = render(<MantineProvider><PhotoUploader /></MantineProvider>);
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const setValue = vi.fn();
  Object.defineProperty(input, "value", { set: setValue, get: () => "", configurable: true });
  fireEvent.change(input, { target: { files: [new File(["x"], "a.png")] } });
  expect(setValue).toHaveBeenCalledWith("");
});
