import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { it, expect, vi, beforeEach } from "vitest";
import { MantineProvider } from "@mantine/core";
import { AngleGallery } from "./AngleGallery";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

const DEFAULT_SETTINGS = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5,
  relief_cap: true, per_region_norm: false,
};

const DEFAULT_BOOK = {
  whole: { palette: [], coverage: [], material: "matte" },
  drawn: [],
  selected: 0,
  schemes: [],
};

function seedAngles(count: number, withPreviews: number[] = []) {
  const angles = Array.from({ length: count }, (_, i) => ({
    id: `a${i}`,
    label: `Angle ${i + 1}`,
    photoId: `ph00${i}`,
    width: 100,
    height: 100,
    qualityChecks: [],
    book: DEFAULT_BOOK,
    settings: DEFAULT_SETTINGS,
    preview: withPreviews.includes(i) ? `data:image/png;base64,FAKE${i}` : undefined,
    resultToken: withPreviews.includes(i) ? `tok${i}` : undefined,
  }));
  useProjectStore.setState({ angles, activeAngle: 0 });
}

beforeEach(() => {
  useProjectStore.setState({ angles: [], activeAngle: 0 });
  vi.restoreAllMocks();
});

it("shows an info message when there are no angles", () => {
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  expect(screen.getByText(/gallery\.no_angles/i)).toBeInTheDocument();
});

it("renders one card per angle", async () => {
  vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC",
    result_token: "tok",
  });
  seedAngles(2);
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  await waitFor(() => {
    expect(screen.getByDisplayValue("Angle 1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Angle 2")).toBeInTheDocument();
  });
});

it("uses store preview for active angle (no extra API call)", async () => {
  const spy = vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC",
    result_token: "tok",
  });
  seedAngles(2, [0]); // angle 0 already has a preview
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  await waitFor(() => {
    // Only angle 1 should have triggered analyze (angle 0 used store preview)
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

it("marks the active angle with an indicator", async () => {
  vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC", result_token: "tok",
  });
  seedAngles(2);
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  await waitFor(() => screen.getAllByAltText(/Angle/));
  expect(screen.getByText(/gallery\.active_badge/i)).toBeInTheDocument();
});

it("shows a loading indicator while preview is fetching", () => {
  // analyze never resolves → stays in loading state
  vi.spyOn(client, "analyze").mockImplementation(() => new Promise(() => {}));
  seedAngles(1);
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  expect(screen.getByText(/gallery\.loading/i)).toBeInTheDocument();
});

it("shows an error state when analyze fails for an angle", async () => {
  vi.spyOn(client, "analyze").mockRejectedValue(new Error("network"));
  seedAngles(1);
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  await waitFor(() => {
    expect(screen.getByText(/gallery\.preview_error/i)).toBeInTheDocument();
  });
});

it("skips fetch for angles without a photoId", async () => {
  const spy = vi.spyOn(client, "analyze").mockResolvedValue({
    preview_png: "data:image/png;base64,ABC", result_token: "tok",
  });
  useProjectStore.setState({
    angles: [{
      id: "a0", label: "No Photo",
      photoId: undefined as any,
      width: undefined, height: undefined,
      qualityChecks: [], book: DEFAULT_BOOK, settings: DEFAULT_SETTINGS,
    }],
    activeAngle: 0,
  });
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  // Brief wait; no fetch should fire
  await new Promise((r) => setTimeout(r, 50));
  expect(spy).not.toHaveBeenCalled();
  expect(screen.getByText(/gallery\.no_photo/i)).toBeInTheDocument();
});

it("clicking a gallery card selects that angle", () => {
  seedAngles(2); // activeAngle = 0
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  fireEvent.click(screen.getByTestId("angle-card-1"));
  expect(useProjectStore.getState().activeAngle).toBe(1);
});

it("gallery exposes rename and delete", () => {
  seedAngles(2);
  render(<MantineProvider><AngleGallery /></MantineProvider>);
  expect(screen.getAllByLabelText("Rename angle").length).toBeGreaterThan(0);
  expect(screen.getAllByLabelText("Remove angle").length).toBeGreaterThan(0);
});
