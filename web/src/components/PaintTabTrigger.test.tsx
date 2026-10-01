import { it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider, Tabs } from "@mantine/core";
import { PaintTabTrigger } from "./PaintTabTrigger";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const ui = (disabled: boolean) => render(
  <MantineProvider>
    <Tabs value="studio"><Tabs.List><PaintTabTrigger disabled={disabled} /></Tabs.List></Tabs>
  </MantineProvider>);

it("explains why the Paint tab is disabled on hover", async () => {
  ui(true);
  expect(screen.getByRole("tab", { name: "tabs.paint" })).toBeDisabled();
  fireEvent.mouseEnter(screen.getByTestId("paint-tab-wrap"));
  await waitFor(() => expect(screen.getByText("tabs.paint_disabled")).toBeTruthy());
});

it("shows no hint once the tab is enabled", async () => {
  ui(false);
  expect(screen.getByRole("tab", { name: "tabs.paint" })).not.toBeDisabled();
  fireEvent.mouseEnter(screen.getByTestId("paint-tab-wrap"));
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByText("tabs.paint_disabled")).toBeNull();
});
