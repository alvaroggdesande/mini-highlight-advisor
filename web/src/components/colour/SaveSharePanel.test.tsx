import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { SaveSharePanel } from "./SaveSharePanel";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("./RecipeSaver", () => ({ RecipeSaver: () => <div>recipe-saver</div> }));
vi.mock("./SchemeManager", () => ({ SchemeManager: () => <div>scheme-manager</div> }));
vi.mock("./RecipeManager", () => ({ RecipeManager: () => <div>recipe-manager</div> }));

it("is collapsed by default and opens to show save, schemes and recipe import/export", () => {
  render(<MantineProvider><SaveSharePanel /></MantineProvider>);
  expect(screen.queryByText("recipe-saver")).toBeNull();
  const btn = screen.getByRole("button", { name: /studio.save_share/ });
  expect(btn.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(btn);
  expect(screen.getByText("recipe-saver")).toBeTruthy();
  expect(screen.getByText("scheme-manager")).toBeTruthy();
  expect(screen.getByText("recipe-manager")).toBeTruthy();
});
