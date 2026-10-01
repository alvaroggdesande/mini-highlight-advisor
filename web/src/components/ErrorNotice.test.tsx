import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import { ErrorNotice } from "./ErrorNotice";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));

const wrap = (ui: React.ReactNode) => render(<MantineProvider>{ui}</MantineProvider>);

describe("ErrorNotice", () => {
  it("shows message and detail", () => {
    wrap(<ErrorNotice message="Could not load" detail="500 boom" />);
    expect(screen.getByText("Could not load")).toBeTruthy();
    expect(screen.getByText("500 boom")).toBeTruthy();
  });
  it("has no retry button without onRetry", () => {
    wrap(<ErrorNotice message="x" />);
    expect(screen.queryByText("errors.retry")).toBeNull();
  });
  it("calls onRetry", () => {
    const onRetry = vi.fn();
    wrap(<ErrorNotice message="x" onRetry={onRetry} />);
    fireEvent.click(screen.getByText("errors.retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
