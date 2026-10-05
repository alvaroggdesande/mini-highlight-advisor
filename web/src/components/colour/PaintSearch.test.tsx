import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { PaintSearch, paintFilter } from "./PaintSearch";
import type { PaintColor } from "../../api/types";

const paints: PaintColor[] = [
  { name: "Mephiston Red", hex: "#9a1115", brand: "Citadel", code: "C-BASE-01" },
  { name: "Flat Red", hex: "#a01c1c", brand: "Vallejo", code: "70957" },
  { name: "Ivory", hex: "#f0e6c8", brand: "Vallejo", code: "70918" },
];
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
vi.mock("../../store/catalogStore", () => ({ useCatalogStore: (sel: any) => sel({ paints }) }));

const opts = paints.map((p) => ({ value: p.code!, label: [p.name, p.code, p.brand].join(" · ") }));

describe("paintFilter", () => {
  it("matches by name, case-insensitive", () => {
    expect(paintFilter({ options: opts, search: "ivo", limit: 50 }).map((o: any) => o.value)).toEqual(["70918"]);
  });
  it("requires every word (brand + name)", () => {
    expect(paintFilter({ options: opts, search: "vallejo red", limit: 50 }).map((o: any) => o.value)).toEqual(["70957"]);
  });
  it("matches by code", () => {
    expect(paintFilter({ options: opts, search: "70918", limit: 50 }).map((o: any) => o.value)).toEqual(["70918"]);
  });
});

describe("PaintSearch", () => {
  it("picking an option hands back the full paint", () => {
    const onPick = vi.fn();
    render(<MantineProvider><PaintSearch onPick={onPick} /></MantineProvider>);
    const input = screen.getByPlaceholderText("colour.search_paint");
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: "ivory" } });
    fireEvent.click(screen.getByText("Ivory"));
    expect(onPick).toHaveBeenCalledWith(paints[2]);
  });
});
