import { describe, it, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { cell, escherichiaClade, wideClade } from "../../test/fixtures/clade";
import CladeTree from "./CladeTree";

function rowFor(name: string) {
  const row = screen.getByText(name).closest("tr");
  if (!row) throw new Error(`No row for ${name}`);
  return row;
}

describe("CladeTree", () => {
  it("renders one column per sample with its label and total", () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    const headers = screen.getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "Taxon",
      "S1sample1,000,000 reads",
      "NTC1NTC1,000,000 reads",
      "NTC2NTCno profile",
    ]);
  });

  it("opens the top two levels and hides deeper taxa off the clicked path", () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    expect(screen.getByText("Escherichia coli")).toBeInTheDocument();
    expect(screen.getByText("Escherichia coli K-12")).toBeInTheDocument();
    expect(screen.queryByText("Escherichia coli str. K-12 substr. MG1655")).not.toBeInTheDocument();
  });

  it("expands a collapsed taxon on click", async () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    await userEvent.click(screen.getByRole("button", { name: "Expand Escherichia coli K-12" }));

    expect(screen.getByText("Escherichia coli str. K-12 substr. MG1655")).toBeInTheDocument();
  });

  it("opens the path to a deep clicked taxon and highlights it", () => {
    const data = escherichiaClade();
    data.clicked = { taxon_id: 511145, name: "MG1655", rank: "strain" };

    renderWithProviders(<CladeTree data={data} />);

    const row = rowFor("Escherichia coli str. K-12 substr. MG1655");
    expect(row).toHaveAttribute("aria-current", "true");
  });

  it("shows clade value with reads per million, and direct reads on parents", () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    // Escherichia in NTC1: 12 in the clade, 3 assigned to the genus itself.
    const ntc1 = within(rowFor("Escherichia")).getAllByRole("cell")[2];
    expect(ntc1).toHaveTextContent("12");
    expect(ntc1).toHaveTextContent("12 rpm");
    expect(ntc1).toHaveTextContent("3 direct");
  });

  it("does not show direct reads on leaves, where they equal the clade", () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    const s1 = within(rowFor("Escherichia coli O157:H7")).getAllByRole("cell")[1];
    expect(s1).not.toHaveTextContent("direct");
  });

  it("distinguishes a missing profile from zero signal", () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    const cells = within(rowFor("Escherichia coli O157:H7")).getAllByRole("cell");
    expect(cells[2]).toHaveTextContent(/^0$/);
    expect(cells[3]).toHaveTextContent("—");
    expect(cells[3]).toHaveAttribute("title", "No profile for this classifier");
  });

  it("flags connector taxa and retired taxids", () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    expect(screen.getByText("Escherichia coli")).toHaveAttribute(
      "title",
      expect.stringContaining("No signal assigned directly")
    );
    expect(within(rowFor("Escherichia coli K-12")).getByText(/retired taxid 12/)).toBeVisible();
  });

  it("folds siblings beyond the per-parent cap into one row", () => {
    // 26 children: 1 with sample reads, 25 only in the control.
    renderWithProviders(<CladeTree data={wideClade()} />);

    expect(screen.getByRole("button", { name: "16 more taxa" })).toBeInTheDocument();
    expect(screen.getByText("Streptomyces sp. C8")).toBeInTheDocument();
    expect(screen.queryByText("Streptomyces sp. C9")).not.toBeInTheDocument();
  });

  it("never folds a taxon with signal in the sample, however weak", () => {
    // 2 reads, the weakest of all 26 children, but the only one in the sample.
    renderWithProviders(<CladeTree data={wideClade()} />);

    expect(screen.getByText("Streptomyces xinghaiensis")).toBeInTheDocument();
  });

  it("shows the combined signal of the folded taxa", () => {
    renderWithProviders(<CladeTree data={wideClade()} />);

    const row = screen.getByRole("button", { name: "16 more taxa" }).closest("tr")!;
    const cells = within(row).getAllByRole("cell");
    expect(cells[1]).toHaveTextContent(/^0$/);
    expect(cells[2]).toHaveTextContent("1,360");
  });

  it("reveals every folded taxon when the summary row is clicked", async () => {
    renderWithProviders(<CladeTree data={wideClade()} />);

    await userEvent.click(screen.getByRole("button", { name: "16 more taxa" }));

    expect(screen.getByText("Streptomyces sp. C24")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /more taxa/ })).not.toBeInTheDocument();
  });

  it("does not fold when a parent has few children", () => {
    renderWithProviders(<CladeTree data={escherichiaClade()} />);

    expect(screen.queryByRole("button", { name: /more taxa/ })).not.toBeInTheDocument();
  });

  it("shows relative abundance without reads per million", () => {
    const data = escherichiaClade();
    data.unit = "fraction";
    data.columns = data.columns.map((c) => ({ ...c, classifier_total: null }));
    data.root.cells = { S1: cell(0, 0.25, null) };

    renderWithProviders(<CladeTree data={data} />);

    const s1 = within(rowFor("Escherichia")).getAllByRole("cell")[1];
    expect(s1).toHaveTextContent("25.00%");
    expect(s1).not.toHaveTextContent("rpm");
  });
});
