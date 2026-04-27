import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AddTaxonModal from "./AddTaxonModal";

function ncbiResponse(id: number, name: string, division = "Viruses") {
  return {
    result: {
      [String(id)]: {
        scientificname: name,
        lineage: "",
        genbankdivision: division,
      },
    },
  };
}

beforeEach(() => {
  vi.spyOn(globalThis, "fetch");
});
afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetchOk(payload: unknown) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: async () => payload,
  } as Response);
}

describe("AddTaxonModal", () => {
  it("looks up a taxon and populates name + kingdom", async () => {
    mockFetchOk(ncbiResponse(11676, "HIV-1", "Viruses"));
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(<AddTaxonModal title="Add" showMinReads={false} onAdd={onAdd} onClose={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText(/e\.g\. 1743/i), "11676");
    await userEvent.click(screen.getByRole("button", { name: /look up/i }));

    expect(await screen.findByText("HIV-1")).toBeInTheDocument();
    expect(screen.getByText("Viruses")).toBeInTheDocument();
  });

  it("shows an error when NCBI returns nothing for the id", async () => {
    mockFetchOk({ result: {} });
    render(<AddTaxonModal title="Add" showMinReads={false} onAdd={vi.fn()} onClose={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText(/e\.g\. 1743/i), "999999");
    await userEvent.click(screen.getByRole("button", { name: /look up/i }));

    expect(await screen.findByText(/could not find taxon in NCBI/i)).toBeInTheDocument();
  });

  it("Add button is disabled until lookup completes, then calls onAdd with the looked-up taxon", async () => {
    mockFetchOk(ncbiResponse(562, "Escherichia coli", "Bacteria"));
    const onAdd = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(<AddTaxonModal title="Add" showMinReads={false} onAdd={onAdd} onClose={onClose} />);

    const addBtn = screen.getByRole("button", { name: /^add$/i });
    expect(addBtn).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText(/e\.g\. 1743/i), "562");
    await userEvent.click(screen.getByRole("button", { name: /look up/i }));
    await screen.findByText("Escherichia coli");

    expect(addBtn).not.toBeDisabled();
    await userEvent.click(addBtn);

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith(562, "Escherichia coli", "Bacteria", null, 3);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("renders the min-reads field only when showMinReads is true", () => {
    const { rerender } = render(
      <AddTaxonModal title="Add" showMinReads={false} onAdd={vi.fn()} onClose={vi.fn()} />
    );
    expect(screen.queryByText(/alert threshold/i)).not.toBeInTheDocument();

    rerender(<AddTaxonModal title="Add" showMinReads onAdd={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText(/alert threshold/i)).toBeInTheDocument();
  });

  it("Cancel button calls onClose", async () => {
    const onClose = vi.fn();
    render(<AddTaxonModal title="Add" showMinReads={false} onAdd={vi.fn()} onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
