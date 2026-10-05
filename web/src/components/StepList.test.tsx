import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { StepList } from "./StepList";
import type { RegionPlanDto } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
const { owned } = vi.hoisted(() => ({ owned: { codes: new Set<string>() } }));
vi.mock("../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ ownedCodes: owned.codes }) }));
const { matchPaint } = vi.hoisted(() => ({ matchPaint: vi.fn() }));
vi.mock("../api/client", () => ({ matchPaint }));

const makeStep = (index: number, isLast: boolean) => ({
  index,
  label: index === 0 ? "Shadow" : "Highlight",
  kind: "band",
  zone_png: "data:image/png;base64,abc",
  cumulative_png: "data:image/png;base64,def",
  exact_png: isLast ? null : "data:image/png;base64,ghi",
  is_last: isLast,
});

const plan: RegionPlanDto = {
  name: "Helmet",
  roles: ["Shadow", "Highlight"],
  coverage: [60, 40],
  steps: [makeStep(0, false), makeStep(1, true)],
};

describe("StepList", () => {
  it("renders the step label for each step", () => {
    render(<MantineProvider><StepList plan={plan} /></MantineProvider>);
    expect(screen.getByText("roles.shadow")).toBeTruthy();
    expect(screen.getByText("roles.highlight")).toBeTruthy();
  });

  it("non-last step renders zone, cumulative, and exact captions", () => {
    render(<MantineProvider><StepList plan={plan} /></MantineProvider>);
    // t() returns the key itself (mocked); non-last step (index 0) has all three
    expect(screen.getAllByText("paint.step_zone").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paint.step_cumulative").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paint.step_exact").length).toBeGreaterThanOrEqual(1);
  });

  it("last-only plan renders zone and cumulative but not exact caption", () => {
    const lastOnlyPlan: RegionPlanDto = { ...plan, steps: [makeStep(0, true)] };
    render(<MantineProvider><StepList plan={lastOnlyPlan} /></MantineProvider>);
    expect(screen.queryByText("paint.step_exact")).toBeNull();
  });

  it("shows the paint name, code and swatch when the step carries a paint", () => {
    const withPaint: RegionPlanDto = { ...plan, steps: [
      { ...makeStep(0, true), paint_name: "Ivory", paint_hex: "#f0e8d0", paint_code: "70.918" },
    ] };
    render(<MantineProvider><StepList plan={withPaint} /></MantineProvider>);
    expect(screen.getByText(/Ivory/)).toBeTruthy();
    expect(screen.getByText(/70\.918/)).toBeTruthy();
    expect(screen.getByTestId("step-swatch")).toBeTruthy();
  });

  it("keeps the plain header when no paint is present", () => {
    render(<MantineProvider><StepList plan={plan} /></MantineProvider>);
    expect(screen.queryByTestId("step-swatch")).toBeNull();
  });

  it("renders the steps hint once", () => {
    render(<MantineProvider><StepList plan={plan} /></MantineProvider>);
    expect(screen.getAllByText("paint.steps_hint")).toHaveLength(1);
  });

  it("catalogue-paint step says whether you own it", () => {
    owned.codes = new Set(["70.918"]);
    const withPaint: RegionPlanDto = { ...plan, steps: [
      { ...makeStep(0, true), paint_name: "Ivory", paint_hex: "#f0e8d0", paint_code: "70.918" },
    ] };
    render(<MantineProvider><StepList plan={withPaint} /></MantineProvider>);
    expect(screen.getByTestId("step-guide").textContent).toContain("colour.owned");
    expect(matchPaint).not.toHaveBeenCalled();
    owned.codes = new Set();
  });

  it("custom-hex step shows the mix guide from your collection", async () => {
    owned.codes = new Set(["A1", "B1"]);
    matchPaint.mockResolvedValue({ tier: "close", phrase: "", name: "Flat Red", delta_e: 3, nearest: [] });
    const custom: RegionPlanDto = { ...plan, steps: [
      { ...makeStep(0, true), paint_name: "custom", paint_hex: "#a51e1e", paint_code: null, paint_finish: "metallic" },
    ] };
    render(<MantineProvider><StepList plan={custom} /></MantineProvider>);
    await waitFor(() => expect(matchPaint).toHaveBeenCalledWith({ hex: "#a51e1e", finish: "metallic", owned_codes: ["A1", "B1"] }));
    expect((await screen.findByTestId("step-guide")).textContent).toBe("≈ Flat Red");
    owned.codes = new Set();
  });
});
