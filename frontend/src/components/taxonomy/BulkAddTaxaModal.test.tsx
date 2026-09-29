import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { server } from "../../test/server";
import BulkAddTaxaModal from "./BulkAddTaxaModal";

const API = "*/api/v1";
const BULK = `${API}/taxon-lists/df-skin/entries/bulk`;

const PREVIEW = {
  to_add_count: 1,
  to_add_sample: [{ taxon_id: 562, taxon_name: "Escherichia coli", superkingdom: "Bacteria" }],
  already_on_list: [1392],
  rejected: [{ taxon_id: 4, reason: "deleted", merged_into: null }],
  replaced: [{ taxon_id: 999, merged_into: 562 }],
  added: 0,
};

function paste(text: string) {
  // fireEvent rather than userEvent.type: pasting thousands of ids key by key is slow.
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
}

describe("BulkAddTaxaModal", () => {
  it("previews every pasted value, then adds exactly the accepted ids", async () => {
    const bodies: { taxon_ids: number[]; dry_run: boolean }[] = [];
    server.use(
      http.post(BULK, async ({ request }) => {
        const body = (await request.json()) as { taxon_ids: number[]; dry_run: boolean };
        bodies.push(body);
        return HttpResponse.json(body.dry_run ? PREVIEW : { ...PREVIEW, added: 1 });
      })
    );
    const onClose = vi.fn();
    renderWithProviders(
      <BulkAddTaxaModal listId="df-skin" listLabel="Skin flora" onClose={onClose} />
    );

    paste("562, 1392, 999, 4, abc");
    await userEvent.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("1 to add")).toBeInTheDocument();
    expect(screen.getByText("2 rejected")).toBeInTheDocument();
    expect(screen.getByText(/Not a taxon id \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/Replaced by the current NCBI id \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("999 → 562")).toBeInTheDocument();
    expect(bodies[0]).toEqual({ taxon_ids: [562, 1392, 999, 4], dry_run: true });

    await userEvent.click(screen.getByRole("button", { name: "Add 1 taxa" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    // The merged id is sent as pasted; the backend replaces it again.
    expect(bodies[1]).toEqual({ taxon_ids: [562, 999], dry_run: false, reason: null });
  });

  it("adds every accepted id of a large paste, not just the named sample", async () => {
    const ids = Array.from({ length: 45_000 }, (_, i) => i + 1);
    let added: number[] = [];
    server.use(
      http.post(BULK, async ({ request }) => {
        const body = (await request.json()) as { taxon_ids: number[]; dry_run: boolean };
        if (!body.dry_run) added = body.taxon_ids;
        return HttpResponse.json({
          to_add_count: 44_999,
          to_add_sample: [{ taxon_id: 2, taxon_name: "T2", superkingdom: null }],
          already_on_list: [],
          rejected: [{ taxon_id: 1, reason: "not_in_taxonomy", merged_into: null }],
          replaced: [],
          added: body.dry_run ? 0 : 44_999,
        });
      })
    );
    renderWithProviders(<BulkAddTaxaModal listId="df-skin" listLabel="Skin" onClose={vi.fn()} />);

    paste(ids.join(","));
    await userEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(await screen.findByText(/first 1 shown/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add 44,999 taxa" }));

    await waitFor(() => expect(added).toHaveLength(44_999));
    expect(added).not.toContain(1);
  });

  it("refuses a paste over the limit before sending it", () => {
    renderWithProviders(<BulkAddTaxaModal listId="df-skin" listLabel="Skin" onClose={vi.fn()} />);
    paste(Array.from({ length: 75_001 }, (_, i) => i + 1).join(","));
    expect(screen.getByText(/at most 75,000 per paste/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check" })).toBeDisabled();
  });

  it("shows the fresh report when the list changed since the preview", async () => {
    server.use(
      http.post(BULK, async ({ request }) => {
        const body = (await request.json()) as { dry_run: boolean };
        if (body.dry_run) return HttpResponse.json(PREVIEW);
        return HttpResponse.json(
          {
            detail: {
              message: "1 taxa cannot be added",
              report: {
                to_add_count: 0,
                to_add_sample: [],
                already_on_list: [],
                rejected: [{ taxon_id: 562, reason: "excluded_by_list", merged_into: null }],
                replaced: [],
                added: 0,
              },
            },
          },
          { status: 422 }
        );
      })
    );
    const onClose = vi.fn();
    renderWithProviders(
      <BulkAddTaxaModal listId="df-skin" listLabel="Skin flora" onClose={onClose} />
    );

    paste("562");
    await userEvent.click(screen.getByRole("button", { name: "Check" }));
    await userEvent.click(await screen.findByRole("button", { name: "Add 1 taxa" }));

    expect(await screen.findByText(/list changed since the preview/i)).toBeInTheDocument();
    expect(screen.getByText("0 to add")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
