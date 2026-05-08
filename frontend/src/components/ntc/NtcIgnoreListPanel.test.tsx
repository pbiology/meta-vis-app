import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { server } from "../../test/server";
import NtcIgnoreListPanel from "./NtcIgnoreListPanel";

const API = "*/api/v1";

function ignoreItem(id: number, name: string, extra: Record<string, unknown> = {}) {
  return {
    taxon_id: id,
    taxon_name: name,
    superkingdom: "Bacteria",
    added_by: "tester",
    added_at: "2026-04-20",
    reason: null,
    ...extra,
  };
}

describe("NtcIgnoreListPanel", () => {
  it("renders rows returned by the API", async () => {
    server.use(
      http.get(`${API}/ntc/ignorelist`, () =>
        HttpResponse.json([ignoreItem(1, "E-coli"), ignoreItem(2, "S-aureus")])
      )
    );

    renderWithProviders(<NtcIgnoreListPanel canEdit canDelete />);
    await waitFor(() => {
      expect(screen.getByText("E coli")).toBeInTheDocument();
      expect(screen.getByText("S aureus")).toBeInTheDocument();
    });
  });

  it("renders an inline error when the ignorelist endpoint 500s", async () => {
    server.use(http.get(`${API}/ntc/ignorelist`, () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<NtcIgnoreListPanel canEdit canDelete />);
    expect(await screen.findByText(/failed to load ntc ignorelist/i)).toBeInTheDocument();
  });

  it("Remove button confirms then deletes via the mutation", async () => {
    let deleted = false;
    server.use(
      http.get(`${API}/ntc/ignorelist`, () => HttpResponse.json([ignoreItem(42, "Foo")])),
      http.delete(`${API}/ntc/ignorelist/42`, () => {
        deleted = true;
        return HttpResponse.json({});
      })
    );

    renderWithProviders(<NtcIgnoreListPanel canEdit canDelete />);
    await userEvent.click(await screen.findByRole("button", { name: "Remove" }));
    // Modal renders a second Remove button — within the dialog title's container.
    const modal = screen.getByText(/remove taxon\?/i).closest("div") as HTMLElement;
    const confirmBtn = within(modal).getByRole("button", { name: "Remove" });
    await userEvent.click(confirmBtn);
    await waitFor(() => expect(deleted).toBe(true));
  });
});
