import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils";
import { server } from "../../test/server";
import NtcContaminantsPanel from "./NtcContaminantsPanel";

const API = "*/api/v1";

function contaminant(id: number, name: string, extra: Record<string, unknown> = {}) {
  return {
    taxon_id: id,
    taxon_name: name,
    superkingdom: "Bacteria",
    min_reads: 5,
    notes: null,
    added_by: "tester",
    added_at: "2026-04-20",
    ...extra,
  };
}

describe("NtcContaminantsPanel", () => {
  it("renders rows returned by the API", async () => {
    server.use(
      http.get(`${API}/ntc/contaminants`, () =>
        HttpResponse.json([contaminant(1, "Cutibacterium-acnes")])
      )
    );

    renderWithProviders(<NtcContaminantsPanel canEdit canDelete />);
    await waitFor(() => {
      expect(screen.getByText("Cutibacterium acnes")).toBeInTheDocument();
      expect(screen.getByText(/> 5 reads/)).toBeInTheDocument();
    });
  });

  it("renders an inline error when the contaminants endpoint 500s", async () => {
    server.use(http.get(`${API}/ntc/contaminants`, () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<NtcContaminantsPanel canEdit canDelete />);
    expect(await screen.findByText(/failed to load known contaminants/i)).toBeInTheDocument();
  });

  it("renders the empty state when no contaminants are configured", async () => {
    renderWithProviders(<NtcContaminantsPanel canEdit canDelete />);
    expect(await screen.findByText(/no known contaminants on the list/i)).toBeInTheDocument();
  });
});
