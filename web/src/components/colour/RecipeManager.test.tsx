import { it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { RecipeManager } from "./RecipeManager";
import { useCatalogStore } from "../../store/catalogStore";
import * as client from "../../api/client";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
beforeEach(() => { vi.restoreAllMocks(); useCatalogStore.setState({ ownedCodes: new Set() }); });

it("collection import from Studio updates the owned set", async () => {
  vi.spyOn(client, "importCollection").mockResolvedValue({ owned: ["V1", "V2"] } as any);
  const { container } = render(<MantineProvider><RecipeManager /></MantineProvider>);
  const input = container.querySelector('input[data-kind="collection"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["{}"], "c.json")] } });
  await waitFor(() => expect(useCatalogStore.getState().ownedCodes.has("V2")).toBe(true));
});

it("shows an error notice when an import fails", async () => {
  vi.spyOn(client, "importRecipes").mockRejectedValue(new Error("400 bad file"));
  const { container } = render(<MantineProvider><RecipeManager /></MantineProvider>);
  const input = container.querySelector('input[data-kind="recipes"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["{}"], "r.json")] } });
  expect(await screen.findByText("errors.import")).toBeTruthy();
});
