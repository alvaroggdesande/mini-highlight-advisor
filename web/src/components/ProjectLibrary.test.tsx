import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { it, expect, vi, beforeEach, afterEach } from "vitest";
import { ProjectLibrary } from "./ProjectLibrary";
import * as client from "../api/client";
import { useProjectStore } from "../store/projectStore";

vi.mock("../api/client");
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, string>) => {
      if (opts?.name) return key.replace("{{name}}", opts.name);
      return key;
    },
  }),
}));

const mockProjects = [
  { slug: "my-mini", name: "My Mini", updated_at: "2026-01-15T00:00:00Z" },
];

beforeEach(() => {
  vi.mocked(client.listProjects).mockResolvedValue(mockProjects);
  vi.mocked(client.saveProjectApi).mockResolvedValue({
    slug: "my-mini", name: "My Mini", updated_at: "2026-01-15T00:00:00Z",
  });
  vi.mocked(client.loadProjectApi).mockResolvedValue({
    name: "My Mini", slug: "my-mini", active_angle: 0, updated_at: "2026-01-15T00:00:00Z",
    angles: [],
  });
  vi.mocked(client.deleteProjectApi).mockResolvedValue(undefined);
  // Reset store
  useProjectStore.setState(useProjectStore.getInitialState(), true);
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("renders collapsed by default", () => {
  render(<ProjectLibrary />);
  expect(screen.getByText(/projects\.react_toggle/i)).toBeInTheDocument();
  expect(screen.queryByPlaceholderText(/react_name_placeholder/i)).not.toBeInTheDocument();
});

it("expands on click and loads project list", async () => {
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => {
    expect(screen.getByPlaceholderText(/react_name_placeholder/i)).toBeInTheDocument();
    expect(screen.getByText("My Mini")).toBeInTheDocument();
  });
});

it("collapses when toggle clicked again", async () => {
  render(<ProjectLibrary />);
  const btn = screen.getByRole("button", { name: /projects\.react_toggle/i });
  fireEvent.click(btn);
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(btn);
  expect(screen.queryByText("My Mini")).not.toBeInTheDocument();
});

it("calls loadProjectApi and initFromProject when Load is clicked", async () => {
  vi.spyOn(useProjectStore.getState(), "initFromProject");
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(screen.getByText(/projects\.react_load/));
  await waitFor(() => expect(client.loadProjectApi).toHaveBeenCalledWith("my-mini"));
});

it("calls deleteProjectApi after confirmation", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(screen.getByText(/projects\.react_delete/));
  await waitFor(() => expect(client.deleteProjectApi).toHaveBeenCalledWith("my-mini"));
});

it("does NOT call deleteProjectApi if user cancels confirmation", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText("My Mini"));
  fireEvent.click(screen.getByText(/projects\.react_delete/));
  expect(client.deleteProjectApi).not.toHaveBeenCalled();
});

it("shows 'No saved projects' when list is empty", async () => {
  vi.mocked(client.listProjects).mockResolvedValue([]);
  render(<ProjectLibrary />);
  fireEvent.click(screen.getByRole("button", { name: /projects\.react_toggle/i }));
  await waitFor(() => screen.getByText(/projects\.react_empty/));
});
