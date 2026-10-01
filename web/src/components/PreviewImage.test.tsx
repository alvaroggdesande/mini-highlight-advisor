import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { PreviewImage } from "./PreviewImage";
import { useProjectStore } from "../store/projectStore";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
const photo = { photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#000000" }], coverage: [1], material: "matte" } };
const wrap = () => render(<MantineProvider><PreviewImage /></MantineProvider>);
beforeEach(() => useProjectStore.setState(useProjectStore.getInitialState(), true));

it("no angle → placeholder", () => { wrap(); expect(screen.getByText("preview.placeholder")).toBeTruthy(); });

it("angle without preview yet → rendering loader, not the placeholder", () => {
  useProjectStore.getState().initFromPhoto(photo as any);
  wrap();
  expect(screen.getByText("preview.rendering")).toBeTruthy();
  expect(screen.queryByText("preview.placeholder")).toBeNull();
});

it("analyzing with a preview → updating badge", () => {
  const st = useProjectStore.getState();
  st.initFromPhoto(photo as any); st.setPreview("data:x", "t"); st.setAnalyzing(true);
  wrap();
  expect(screen.getByText("preview.updating")).toBeTruthy();
});

it("error → friendly notice whose Retry bumps the nonce", () => {
  const st = useProjectStore.getState();
  st.initFromPhoto(photo as any); st.setError("500 boom");
  wrap();
  expect(screen.getByText("errors.analyze")).toBeTruthy();
  fireEvent.click(screen.getByText("errors.retry"));
  expect(useProjectStore.getState().angles[0].analyzeNonce).toBe(1);
});
