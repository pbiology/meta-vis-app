import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { server } from "../../test/server";
import TaxonListEntriesPanel from "./TaxonListEntriesPanel";

const API = "*/api/v1";

function last<T>(items: T[]): T | undefined {
  return items[items.length - 1];
}

function entry(taxon_id: number) {
  return {
    list_id: "df-big",
    taxon_id,
    taxon_name: `Taxon ${taxon_id}`,
    superkingdom: "Bacteria",
    reason: null,
    min_reads: null,
    added_by: "tester",
    added_at: "2026-09-29",
    updated_by: null,
    updated_at: null,
  };
}

describe("TaxonListEntriesPanel", () => {
  it("pages through a large list and searches on the server", async () => {
    const requests: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/taxon-lists/df-big/entries`, ({ request }) => {
        const params = new URL(request.url).searchParams;
        requests.push(params);
        const offset = Number(params.get("offset"));
        return HttpResponse.json({
          items: [entry(offset + 1)],
          total: params.get("q") ? 1 : 45_000,
          offset,
          limit: 100,
        });
      })
    );
    renderWithProviders(
      <TaxonListEntriesPanel listId="df-big" listLabel="Big" canEdit={false} canDelete={false} />
    );

    expect(await screen.findByText("45,000 taxa")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 450")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Taxon 101")).toBeInTheDocument();
    expect(last(requests)?.get("offset")).toBe("100");

    await userEvent.type(screen.getByLabelText("Search taxa on this list"), "562");
    await waitFor(() => expect(last(requests)?.get("q")).toBe("562"));
    expect(last(requests)?.get("offset")).toBe("0");
    expect(await screen.findByText("1 taxon")).toBeInTheDocument();
  });

  it("shows the retired ids an entry also matches", async () => {
    server.use(
      http.get(`${API}/taxon-lists/df-big/entries`, () =>
        HttpResponse.json({
          items: [{ ...entry(28116), merged_ids: [1912894, 1912896] }],
          total: 1,
          offset: 0,
          limit: 100,
        })
      )
    );
    renderWithProviders(
      <TaxonListEntriesPanel listId="df-big" listLabel="Big" canEdit={false} canDelete={false} />
    );
    expect(await screen.findByText("also matches 1912894, 1912896")).toBeInTheDocument();
  });
});
