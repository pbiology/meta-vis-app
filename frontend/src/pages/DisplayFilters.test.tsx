import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import { server } from "../test/server";
import DisplayFilters from "./DisplayFilters";

const API = "*/api/v1";

const SKIN = {
  list_id: "df-skin",
  kind: "display_filter",
  name: "Skin flora",
  description: null,
  system: false,
  created_by: "alice",
  created_at: "2026-09-28",
  updated_at: "2026-09-28",
  entry_count: 0,
};

function withLists(lists: object[]) {
  server.use(http.get(`${API}/taxon-lists`, () => HttpResponse.json(lists)));
}

describe("DisplayFilters", () => {
  it("readers can look but not create, rename or delete", async () => {
    withLists([SKIN]);
    renderWithProviders(<DisplayFilters />, { roles: ["reader"] });

    expect(await screen.findByRole("heading", { name: "Skin flora" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new list/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete list" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add taxon/i })).not.toBeInTheDocument();
  });

  it("writers create lists but cannot delete them", async () => {
    let posted: unknown = null;
    withLists([SKIN]);
    server.use(
      http.post(`${API}/taxon-lists`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json({ ...SKIN, list_id: "df-new", name: "Kit" }, { status: 201 });
      })
    );
    renderWithProviders(<DisplayFilters />, { roles: ["writer"] });

    await screen.findByRole("heading", { name: "Skin flora" });
    expect(screen.queryByRole("button", { name: "Delete list" })).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("New list name"), "Kit");
    await userEvent.click(screen.getByRole("button", { name: /new list/i }));

    await waitFor(() => expect(posted).toEqual({ kind: "display_filter", name: "Kit" }));
  });

  it("admins delete a list and it is turned off for them", async () => {
    let deleted = false;
    let prefsPatch: unknown = null;
    withLists([SKIN]);
    server.use(
      http.get(`${API}/users/me/preferences`, () =>
        HttpResponse.json({
          preferred_kingdoms: ["Viruses"],
          visible_analysis_types: ["shotgun", "amplicon"],
          active_display_filters: [SKIN.list_id],
        })
      ),
      http.delete(`${API}/taxon-lists/${SKIN.list_id}`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
      http.patch(`${API}/users/me/preferences`, async ({ request }) => {
        prefsPatch = await request.json();
        return HttpResponse.json({
          preferred_kingdoms: ["Viruses"],
          visible_analysis_types: ["shotgun", "amplicon"],
          active_display_filters: [],
        });
      })
    );
    renderWithProviders(<DisplayFilters />, { roles: ["admin"] });

    await userEvent.click(await screen.findByRole("button", { name: "Delete list" }));
    const dialog = screen.getByText("Delete list?").closest("div") as HTMLElement;
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleted).toBe(true));
    await waitFor(() => expect(prefsPatch).toEqual({ active_display_filters: [] }));
  });
});
