import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { SchemeManager } from "./SchemeManager";
import { useProjectStore } from "../../store/projectStore";
import type { PhotoResponse } from "../../api/types";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const photo = (): PhotoResponse => ({
  photo_id: "p1", width: 10, height: 10, quality_checks: [],
  default_whole: { palette: [{ name: "a", hex: "#111" }], coverage: [1], material: "matte" },
});
const reset = () => useProjectStore.setState(useProjectStore.getInitialState(), true);

describe("SchemeManager", () => {
  beforeEach(() => { reset(); useProjectStore.getState().initFromPhoto(photo()); });

  it("saves a scheme when name entered and Save clicked", () => {
    render(<MantineProvider><SchemeManager /></MantineProvider>);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "My Scheme" } });
    fireEvent.click(screen.getByText("schemes.save"));
    expect(screen.getByText("My Scheme")).toBeTruthy();
  });

  it("deletes a scheme", () => {
    useProjectStore.getState().saveScheme("ToDelete");
    render(<MantineProvider><SchemeManager /></MantineProvider>);
    fireEvent.click(screen.getByText("schemes.delete"));
    expect(screen.queryByText("ToDelete")).toBeNull();
  });

  it("applies a scheme by clicking Apply", () => {
    useProjectStore.getState().saveScheme("snap");
    const spy = vi.spyOn(useProjectStore.getState(), "applyScheme");
    render(<MantineProvider><SchemeManager /></MantineProvider>);
    fireEvent.click(screen.getByText("schemes.apply"));
    expect(spy).toHaveBeenCalled();
  });
});
