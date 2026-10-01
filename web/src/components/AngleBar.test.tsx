import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { useProjectStore } from "../store/projectStore";
import { AngleBar } from "./AngleBar";
import * as client from "../api/client";
import * as ds from "../lib/downscale";

afterEach(() => vi.restoreAllMocks());

const photo = (id: string) => ({ photo_id: id, width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000" }], coverage: [1], material: "matte" } });

describe("AngleBar", () => {
  beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

  it("switches the active angle when a different angle is picked", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p0"));
    st.addAngle(photo("p1"));      // active -> 1
    render(<MantineProvider><AngleBar /></MantineProvider>);
    fireEvent.click(screen.getByText("angle 1"));
    expect(useProjectStore.getState().activeAngle).toBe(0);
  });

  it("does not expose rename or delete in the bar", () => {
    const st = useProjectStore.getState();
    st.initFromPhoto(photo("p0"));
    st.addAngle(photo("p1"));
    render(<MantineProvider><AngleBar /></MantineProvider>);
    expect(screen.queryByLabelText("Rename angle")).toBeNull();
    expect(screen.queryByLabelText("Remove angle")).toBeNull();
  });

  it("+ angle downscales the photo before uploading", async () => {
    useProjectStore.getState().initFromPhoto(photo("p0"));
    const small = new Blob(["small"]);
    const down = vi.spyOn(ds, "downscaleImage").mockResolvedValue(small);
    const up = vi.spyOn(client, "uploadPhoto").mockResolvedValue(photo("p1") as any);
    const { container } = render(<MantineProvider><AngleBar /></MantineProvider>);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["big"], "b.png")] } });
    await waitFor(() => expect(up).toHaveBeenCalledWith(small, "b.png"));
    expect(down).toHaveBeenCalled();
  });
});
