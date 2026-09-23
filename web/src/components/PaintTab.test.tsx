import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { PaintTab } from "./PaintTab";
import { useProjectStore } from "../store/projectStore";
import * as client from "../api/client";
import type { StepsResponse, Settings } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./StepList", () => ({
  StepList: ({ plans }: { plans: unknown[] }) => (
    <div data-testid="step-list">{plans.length} plans</div>
  ),
}));

const SETTINGS: Settings = {
  edge_hl: true, edge_extreme: false, edge_sens: 0.5, relief_cap: true, per_region_norm: false,
};
const EMPTY_RESPONSE: StepsResponse = { plans: [] };

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

  it("shows loading while fetching", () => {
    vi.spyOn(client, "fetchSteps").mockReturnValue(new Promise(() => {}));
    render(<MantineProvider><PaintTab /></MantineProvider>);
    // Loader renders a span with class containing "mantine-Loader-root"
    expect(document.querySelector('[class*="mantine-Loader-root"]')).toBeTruthy();
  });

  it("fetches steps with the current token on mount and renders StepList", async () => {
    vi.spyOn(client, "fetchSteps").mockResolvedValue(EMPTY_RESPONSE);
    render(<MantineProvider><PaintTab /></MantineProvider>);
    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());
    expect(client.fetchSteps).toHaveBeenCalledWith("tok123");
  });

  it("re-analyzes and retries on TokenExpiredError", async () => {
    vi.spyOn(client, "fetchSteps")
      .mockRejectedValueOnce(new client.TokenExpiredError())
      .mockResolvedValueOnce(EMPTY_RESPONSE);
    vi.spyOn(client, "analyze").mockResolvedValue({
      preview_png: "data:image/png;base64,y",
      result_token: "newTok",
    });
    render(<MantineProvider><PaintTab /></MantineProvider>);
    await waitFor(() => expect(screen.getByTestId("step-list")).toBeTruthy());
    expect(client.analyze).toHaveBeenCalledOnce();
    expect(client.fetchSteps).toHaveBeenCalledTimes(2);
    expect(client.fetchSteps).toHaveBeenLastCalledWith("newTok");
  });
});
