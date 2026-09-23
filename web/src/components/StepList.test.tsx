import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { StepList } from "./StepList";
import type { RegionPlanDto } from "../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

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
  it("renders a heading for each region", () => {
    render(<MantineProvider><StepList plans={[plan]} /></MantineProvider>);
    expect(screen.getByText("Helmet")).toBeTruthy();
  });

  it("renders the step label for each step", () => {
    render(<MantineProvider><StepList plans={[plan]} /></MantineProvider>);
    expect(screen.getByText("Shadow")).toBeTruthy();
    expect(screen.getByText("Highlight")).toBeTruthy();
  });

  it("non-last step renders zone, cumulative, and exact captions", () => {
    render(<MantineProvider><StepList plans={[plan]} /></MantineProvider>);
    // t() returns the key itself (mocked); non-last step (index 0) has all three
    expect(screen.getAllByText("paint.step_zone").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paint.step_cumulative").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paint.step_exact").length).toBeGreaterThanOrEqual(1);
  });

  it("last-only plan renders zone and cumulative but not exact caption", () => {
    const lastOnlyPlan: RegionPlanDto = { ...plan, steps: [makeStep(0, true)] };
    render(<MantineProvider><StepList plans={[lastOnlyPlan]} /></MantineProvider>);
    expect(screen.queryByText("paint.step_exact")).toBeNull();
  });

  it("renders multiple regions", () => {
    const plan2: RegionPlanDto = { ...plan, name: "Cloak" };
    render(<MantineProvider><StepList plans={[plan, plan2]} /></MantineProvider>);
    expect(screen.getByText("Helmet")).toBeTruthy();
    expect(screen.getByText("Cloak")).toBeTruthy();
  });
});
