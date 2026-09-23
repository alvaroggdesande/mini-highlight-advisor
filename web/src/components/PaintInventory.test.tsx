import { render, screen, fireEvent } from "@testing-library/react";
import { it, expect, vi, beforeEach } from "vitest";
import { MantineProvider } from "@mantine/core";
import { PaintInventory } from "./PaintInventory";
import { useCatalogStore } from "../store/catalogStore";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => {
    if (o) return `${k}:${JSON.stringify(o)}`;
    return k;
  }}),
}));

const fakePaint = (code: string, name = `Paint ${code}`, range = "Base") => ({
  name, hex: "#aabbcc", code, finish: "matte", paint_range: range, brand: "Citadel",
});

function seedCatalog(codes: string[], ownedCodes: string[] = []) {
  useCatalogStore.setState({
    paints: codes.map((c) => fakePaint(c)),
    status: "ready",
    ownedCodes: new Set(ownedCodes),
    collectionStatus: "ready",
  });
}

beforeEach(() => {
  useCatalogStore.setState({ paints: [], status: "idle", ownedCodes: new Set(), collectionStatus: "idle" });
  vi.restoreAllMocks();
});

it("renders a row for each paint in the catalog", () => {
  seedCatalog(["C1", "C2", "C3"]);
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  expect(screen.getByText("Paint C1")).toBeInTheDocument();
  expect(screen.getByText("Paint C2")).toBeInTheDocument();
  expect(screen.getByText("Paint C3")).toBeInTheDocument();
});

it("owned paints have their checkbox checked", () => {
  seedCatalog(["C1", "C2"], ["C1"]);
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  const checkboxes = screen.getAllByRole("checkbox");
  expect(checkboxes[0]).toBeChecked();
  expect(checkboxes[1]).not.toBeChecked();
});

it("clicking an unchecked row calls toggleOwned", async () => {
  seedCatalog(["C1"], []);
  const toggleSpy = vi.fn().mockResolvedValue(undefined);
  useCatalogStore.setState({ toggleOwned: toggleSpy } as any);
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(toggleSpy).toHaveBeenCalledWith("C1");
});

it("clicking an owned row calls toggleOwned to unmark it", async () => {
  seedCatalog(["C1"], ["C1"]);
  const toggleSpy = vi.fn().mockResolvedValue(undefined);
  useCatalogStore.setState({ toggleOwned: toggleSpy } as any);
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(toggleSpy).toHaveBeenCalledWith("C1");
});

it("search filters catalog rows by name", () => {
  seedCatalog(["C1", "C2"], []);
  useCatalogStore.setState({
    paints: [fakePaint("C1", "Abaddon Black"), fakePaint("C2", "White Scar")],
    status: "ready",
  });
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  const search = screen.getByRole("searchbox");
  fireEvent.change(search, { target: { value: "black" } });
  expect(screen.getByText("Abaddon Black")).toBeInTheDocument();
  expect(screen.queryByText("White Scar")).not.toBeInTheDocument();
});

it("search filters by code", () => {
  seedCatalog([], []);
  useCatalogStore.setState({
    paints: [fakePaint("C1", "Paint A"), fakePaint("C2", "Paint B")],
    status: "ready",
  });
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "C2" } });
  expect(screen.queryByText("Paint A")).not.toBeInTheDocument();
  expect(screen.getByText("Paint B")).toBeInTheDocument();
});

it("shows owned and total count", () => {
  seedCatalog(["C1", "C2", "C3"], ["C1", "C2"]);
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  expect(screen.getByText(/2.*3|3.*2/)).toBeInTheDocument();
});

it("shows empty catalog message when no paints loaded", () => {
  render(<MantineProvider><PaintInventory /></MantineProvider>);
  expect(screen.getByText(/paints\.loading/i)).toBeInTheDocument();
});
