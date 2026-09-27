import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { PaintTab } from "./PaintTab";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";
import type { StepsResponse, PlansManifest, RegionPlanDto, Settings } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./StepList", () => ({
  StepList: ({ plan }: { plan: RegionPlanDto }) => (
    <div data-testid="step-list">{plan.name}</div>
  ),
}));

const SETTINGS: Settings = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5, relief_cap: true, per_region_norm: false,
};

const MANIFEST: PlansManifest = { plans: [{ name: "Whole mini" }, { name: "Cloak" }] };
const planOf = (name: string): StepsResponse => ({
  plans: [{ name, roles: ["Shadow"], coverage: [100], steps: [] }],
});

beforeEach(() => {
  vi.restoreAllMocks();
  useProjectStore.setState({
    activeAngle: 0,
    angles: [{
      id: "a1", label: "Front", photoId: "abc123", width: 30, height: 40,
      qualityChecks: [], settings: SETTINGS,
      book: {
        whole: { palette: [], coverage: [], material: "matte" },
        drawn: [], selected: 0, schemes: [],
      },
      preview: "data:image/png;base64,xxx",
      resultToken: "tok123",
    }],
  });
});

describe("PaintTab", () => {
  it("shows no_preview when result token is absent", () => {
    useProjectStore.setState((s) => ({
      ...s,
      angles: [{ ...s.angles[0], resultToken: undefined }],
    }));
    render(<MantineProvider><PaintTab /></MantineProvider>);
    expect(screen.getByText("paint.no_preview")).toBeTruthy();
  });

  it("shows loading while fetching the region manifest", () => {
    vi.spyOn(client, "fetchPlanNames").mockReturnValue(new Promise(() => {}));
    render(<MantineProvider><PaintTab /></MantineProvider>);
    expect(document.querySelector('[class*="mantine-Loader-root"]')).toBeTruthy();
  });

  it("renders a tab per region and shows the first region's steps", async () => {
    vi.spyOn(client, "fetchPlanNames").mockResolvedValue(MANIFEST);
    const fetchSteps = vi.spyOn(client, "fetchSteps")
      .mockImplementation(async (_t, plan) => planOf(plan!));
    render(<MantineProvider><PaintTab /></MantineProvider>);

    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());
    // One tab per region name
    expect(screen.getByRole("tab", { name: "Whole mini" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Cloak" })).toBeTruthy();
    // Only the first region's steps were fetched, and they are shown
    expect(fetchSteps).toHaveBeenCalledWith("tok123", "Whole mini");
    expect(fetchSteps).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("step-list").textContent).toBe("Whole mini");
  });

  it("fetches a region's steps when its tab is selected", async () => {
    vi.spyOn(client, "fetchPlanNames").mockResolvedValue(MANIFEST);
    const fetchSteps = vi.spyOn(client, "fetchSteps")
      .mockImplementation(async (_t, plan) => planOf(plan!));
    render(<MantineProvider><PaintTab /></MantineProvider>);
    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());

    fireEvent.click(screen.getByRole("tab", { name: "Cloak" }));
    await waitFor(() => expect(screen.getByTestId("step-list").textContent).toBe("Cloak"));
    expect(fetchSteps).toHaveBeenCalledWith("tok123", "Cloak");
  });

  it("does not refetch a region already loaded (cache)", async () => {
    vi.spyOn(client, "fetchPlanNames").mockResolvedValue(MANIFEST);
    const fetchSteps = vi.spyOn(client, "fetchSteps")
      .mockImplementation(async (_t, plan) => planOf(plan!));
    render(<MantineProvider><PaintTab /></MantineProvider>);
    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());

    fireEvent.click(screen.getByRole("tab", { name: "Cloak" }));
    await waitFor(() => expect(screen.getByTestId("step-list").textContent).toBe("Cloak"));
    fireEvent.click(screen.getByRole("tab", { name: "Whole mini" }));
    await waitFor(() => expect(screen.getByTestId("step-list").textContent).toBe("Whole mini"));

    // Whole mini + Cloak, each fetched exactly once — no refetch on return
    expect(fetchSteps).toHaveBeenCalledTimes(2);
  });

  it("re-analyzes and retries when the manifest token has expired", async () => {
    vi.spyOn(client, "fetchPlanNames")
      .mockRejectedValueOnce(new client.TokenExpiredError())
      .mockResolvedValueOnce(MANIFEST);
    vi.spyOn(client, "fetchSteps").mockImplementation(async (_t, plan) => planOf(plan!));
    vi.spyOn(client, "analyze").mockResolvedValue({
      preview_png: "data:image/png;base64,y",
      result_token: "newTok",
    });
    render(<MantineProvider><PaintTab /></MantineProvider>);

    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());
    expect(client.analyze).toHaveBeenCalledOnce();
    expect(client.fetchPlanNames).toHaveBeenCalledTimes(2);
    expect(client.fetchPlanNames).toHaveBeenLastCalledWith("newTok");
  });
});
