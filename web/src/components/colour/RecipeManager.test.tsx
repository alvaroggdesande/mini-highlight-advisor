import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RecipeManager } from "./RecipeManager";
import * as client from "../../api/client";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
beforeEach(() => { vi.restoreAllMocks(); });

it("offers recipe import/export only — no collection buttons", () => {
  const { container } = render(<MantineProvider><RecipeManager /></MantineProvider>);
  expect(screen.getByText("recipes.export")).toBeTruthy();
  expect(screen.getByText("recipes.import")).toBeTruthy();
  expect(screen.queryByText("recipes.collection_export")).toBeNull();
  expect(screen.queryByText("recipes.collection_import")).toBeNull();
  expect(container.querySelector('input[data-kind="collection"]')).toBeNull();
});

it("shows an error notice when an import fails", async () => {
  vi.spyOn(client, "importRecipes").mockRejectedValue(new Error("400 bad file"));
  const { container } = render(<MantineProvider><RecipeManager /></MantineProvider>);
  const input = container.querySelector('input[data-kind="recipes"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["{}"], "r.json")] } });
  expect(await screen.findByText("errors.import")).toBeTruthy();
});
