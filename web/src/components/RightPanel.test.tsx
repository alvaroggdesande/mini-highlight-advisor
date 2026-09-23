import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RightPanel } from "./RightPanel";

vi.mock("./ManagePanel", () => ({ ManagePanel: () => <div>ManagePanel</div> }));
vi.mock("./colour/ColourPanel", () => ({ ColourPanel: () => <div>ColourPanel</div> }));
vi.mock("./TechniquePanel", () => ({ TechniquePanel: () => <div>TechniquePanel</div> }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe("RightPanel", () => {
  it("renders ManagePanel by default", () => {
    render(<MantineProvider><RightPanel /></MantineProvider>);
    expect(screen.getByText("ManagePanel")).toBeTruthy();
  });

  it("clicking Colour tab renders ColourPanel", () => {
    render(<MantineProvider><RightPanel /></MantineProvider>);
    fireEvent.click(screen.getByText("tabs.colour"));
    expect(screen.getByText("ColourPanel")).toBeTruthy();
    // Verify that ManagePanel is not visible in the active tabpanel
    expect(screen.queryByText("ManagePanel")).not.toBeVisible();
  });

  it("clicking Technique tab renders TechniquePanel", () => {
    render(<MantineProvider><RightPanel /></MantineProvider>);
    fireEvent.click(screen.getByText("tabs.technique"));
    expect(screen.getByText("TechniquePanel")).toBeTruthy();
  });
});
