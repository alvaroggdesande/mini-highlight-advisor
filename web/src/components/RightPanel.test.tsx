import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RightPanel } from "./RightPanel";

vi.mock("./ManagePanel", () => ({ ManagePanel: () => <div>ManagePanel</div> }));
vi.mock("./colour/ColourPanel", () => ({ ColourPanel: () => <div>ColourPanel</div> }));
vi.mock("./TechniquePanel", () => ({ TechniquePanel: () => <div>TechniquePanel</div> }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe("RightPanel", () => {
  it("renders ManagePanel by default", () => {
    render(<RightPanel />);
    expect(screen.getByText("ManagePanel")).toBeTruthy();
  });

  it("clicking Colour tab renders ColourPanel", () => {
    render(<RightPanel />);
    fireEvent.click(screen.getByText("tabs.colour"));
    expect(screen.getByText("ColourPanel")).toBeTruthy();
    expect(screen.queryByText("ManagePanel")).toBeNull();
  });

  it("clicking Technique tab renders TechniquePanel", () => {
    render(<RightPanel />);
    fireEvent.click(screen.getByText("tabs.technique"));
    expect(screen.getByText("TechniquePanel")).toBeTruthy();
  });
});
