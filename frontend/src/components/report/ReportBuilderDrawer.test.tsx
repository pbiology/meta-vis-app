import { describe, it, expect, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import ReportBuilderDrawer, { type DrawerTaxonInfo } from "./ReportBuilderDrawer";
import { ReportBuilderProvider, useReportBuilder } from "../../context/ReportBuilderContext";

const SAMPLE_ID = "sample-1";

const lookup = new Map<number, DrawerTaxonInfo>([
  [11676, { taxon_id: 11676, name: "HIV-1", rank: "species" }],
  [562, { taxon_id: 562, name: "Escherichia coli", rank: "species" }],
]);

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
  return <ReportBuilderProvider>{children}</ReportBuilderProvider>;
}

// Test helper: a child that mutates the report builder so we can seed selections
// without going through TaxonomyTable in this isolated test.
function Seeder({ taxonIds }: Readonly<{ taxonIds: number[] }>) {
  const { addTaxon } = useReportBuilder();
  return (
    <button data-testid="seed" onClick={() => taxonIds.forEach((id) => addTaxon(SAMPLE_ID, id))}>
      seed
    </button>
  );
}

beforeEach(() => {
  sessionStorage.clear();
});

describe("ReportBuilderDrawer", () => {
  it("renders nothing when no taxa are selected", () => {
    render(
      <Wrapper>
        <ReportBuilderDrawer sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    expect(screen.queryByLabelText("Report builder")).not.toBeInTheDocument();
  });

  it("renders selected taxa with names + count", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676, 562]} />
        <ReportBuilderDrawer sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));

    expect(screen.getByLabelText("Report builder")).toBeInTheDocument();
    expect(screen.getByText("2 taxa selected")).toBeInTheDocument();
    expect(screen.getByText("HIV-1")).toBeInTheDocument();
    expect(screen.getByText("Escherichia coli")).toBeInTheDocument();
  });

  it("singularises the count for one taxon", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676]} />
        <ReportBuilderDrawer sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    expect(screen.getByText("1 taxon selected")).toBeInTheDocument();
  });

  it("removes a taxon when × is clicked", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676, 562]} />
        <ReportBuilderDrawer sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByLabelText("Remove HIV-1 from report"));
    expect(screen.queryByText("HIV-1")).not.toBeInTheDocument();
    expect(screen.getByText("Escherichia coli")).toBeInTheDocument();
    expect(screen.getByText("1 taxon selected")).toBeInTheDocument();
  });

  it("clears all taxa when Clear all is clicked", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676, 562]} />
        <ReportBuilderDrawer sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByRole("button", { name: /clear all/i }));
    expect(screen.queryByLabelText("Report builder")).not.toBeInTheDocument();
  });

  it("falls back to a placeholder when a taxon is not in the lookup", async () => {
    const partial = new Map<number, DrawerTaxonInfo>();
    render(
      <Wrapper>
        <Seeder taxonIds={[99999]} />
        <ReportBuilderDrawer sampleId={SAMPLE_ID} taxonLookup={partial} />
      </Wrapper>
    );
    // Seed inside act so the state update flushes before assertions.
    await act(async () => {
      await userEvent.click(screen.getByTestId("seed"));
    });
    expect(screen.getByText("Taxon 99999")).toBeInTheDocument();
  });
});
