import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import UserPreferences from "./UserPreferences";

const API = "*/api/v1";

function list(list_id: string, name: string, entry_count: number) {
  return {
    list_id,
    kind: "display_filter",
    name,
    description: null,
    system: false,
    created_by: "tester",
    created_at: "2026-09-29",
    updated_at: "2026-09-29",
    entry_count,
  };
}

function savedPreferences(active: string[]) {
  server.use(
    http.get(`${API}/users/me/preferences`, () =>
      HttpResponse.json({
        preferred_kingdoms: ["Bacteria"],
        visible_analysis_types: ["shotgun"],
        active_display_filters: active,
      })
    )
  );
}

describe("UserPreferences — display filters", () => {
  it("ticks the saved lists and saves a new selection with the other fields", async () => {
    let patched: unknown = null;
    savedPreferences(["df-skin"]);
    server.use(
      http.get(`${API}/taxon-lists`, () =>
        HttpResponse.json([list("df-skin", "Skin flora", 12), list("df-kit", "Kit", 45_000)])
      ),
      http.patch(`${API}/users/me/preferences`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        patched = body;
        return HttpResponse.json(body);
      })
    );
    renderWithProviders(<UserPreferences />);

    const skin = await screen.findByRole("checkbox", { name: /Skin flora/ });
    const kit = screen.getByRole("checkbox", { name: /Kit/ });
    expect(skin).toBeChecked();
    expect(kit).not.toBeChecked();
    expect(screen.getByText("45,000 taxa")).toBeInTheDocument();

    await userEvent.click(kit);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(patched).toEqual({
        preferred_kingdoms: ["Bacteria"],
        visible_analysis_types: ["shotgun"],
        active_display_filters: ["df-skin", "df-kit"],
      })
    );
  });

  it("starts from the saved preferences, not the defaults", async () => {
    savedPreferences([]);
    renderWithProviders(<UserPreferences />);
    // Bacteria is saved; the built-in default would be Viruses.
    expect(await screen.findByRole("checkbox", { name: "Bacteria" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Viruses" })).not.toBeChecked();
  });

  it("shows the empty state and a link to manage lists", async () => {
    savedPreferences([]);
    renderWithProviders(<UserPreferences />);
    expect(await screen.findByText("No display filters yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage display filters" })).toHaveAttribute(
      "href",
      "/display-filters"
    );
  });
});
