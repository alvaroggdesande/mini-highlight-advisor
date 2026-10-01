import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { QualityAlert } from "./QualityAlert";
import { useProjectStore } from "../store/projectStore";
import type { PhotoResponse, QualityCheck } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const photo = (id: string, checks: QualityCheck[]): PhotoResponse => ({
  photo_id: id, width: 10, height: 10, quality_checks: checks,
  default_whole: { palette: [{ name: "a", hex: "#111" }], coverage: [1], material: "matte" },
});
const ok = (id: string): QualityCheck => ({ id, label: id, ok: true, detail: "fine" });
const bad = (id: string): QualityCheck => ({ id, label: id, ok: false, detail: `raw ${id}` });
const ui = () => render(<MantineProvider><QualityAlert /></MantineProvider>);

describe("QualityAlert", () => {
  beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

  it("renders nothing when every check passes", () => {
    useProjectStore.getState().initFromPhoto(photo("p1", [ok("lighting"), ok("focus")]));
    ui();
    expect(screen.queryByText("quality.title")).toBeNull();
  });

  it("lists only failing checks with translated advice", () => {
    useProjectStore.getState().initFromPhoto(photo("p1", [bad("lighting"), ok("focus"), bad("resolution")]));
    ui();
    expect(screen.getByText("quality.title")).toBeTruthy();
    expect(screen.getByText("quality.lighting")).toBeTruthy();
    expect(screen.getByText("quality.resolution")).toBeTruthy();
    expect(screen.queryByText("quality.focus")).toBeNull();
  });

  it("falls back to the server detail when the check has no known id", () => {
    useProjectStore.getState().initFromPhoto(photo("p1", [{ label: "Old", ok: false, detail: "legacy advice" }]));
    ui();
    expect(screen.getByText("legacy advice")).toBeTruthy();
  });

  it("can be dismissed for the current photo", () => {
    useProjectStore.getState().initFromPhoto(photo("p1", [bad("focus")]));
    ui();
    fireEvent.click(screen.getByRole("button", { name: "quality.dismiss" }));
    expect(screen.queryByText("quality.title")).toBeNull();
  });

  it("toggles the photo tips inline", () => {
    useProjectStore.getState().initFromPhoto(photo("p1", [bad("focus")]));
    ui();
    expect(screen.queryByText("tips.raking")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "quality.tips" }));
    expect(screen.getByText("tips.raking")).toBeTruthy();
  });
});
