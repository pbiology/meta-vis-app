import { describe, it, expect, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import ReportCart, { type CartTaxonInfo } from "./ReportCart";
import { ReportBuilderProvider, useReportBuilder } from "../../context/ReportBuilderContext";

const SAMPLE_ID = "sample-1";

const lookup = new Map<number, CartTaxonInfo>([
  [11676, { taxon_id: 11676, name: "HIV-1", rank: "species" }],
  [562, { taxon_id: 562, name: "Escherichia coli", rank: "species" }],
]);

function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
  return <ReportBuilderProvider>{children}</ReportBuilderProvider>;
}

// Seeds the report builder so we can test the cart without going through
// TaxonomyTable. The button is rendered outside the cart container, so
// clicking it doesn't accidentally trigger the cart's outside-click handler.
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

describe("ReportCart", () => {
  it("renders nothing when no taxa are selected", () => {
    render(
      <Wrapper>
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    expect(screen.queryByRole("button", { name: /report cart/i })).not.toBeInTheDocument();
  });

  it("shows the pill with a count when taxa are selected, popover starts closed", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676, 562]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));

    expect(screen.getByRole("button", { name: /report cart/i })).toHaveTextContent(/report · 2/i);
    // Popover content not visible until the pill is clicked.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the popover with items when the pill is clicked", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676, 562]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByRole("button", { name: /report cart/i }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("2 taxa in report");
    expect(dialog).toHaveTextContent("HIV-1");
    expect(dialog).toHaveTextContent("Escherichia coli");
  });

  it("singularises the count for one taxon", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByRole("button", { name: /report cart/i }));
    expect(screen.getByRole("dialog")).toHaveTextContent("1 taxon in report");
  });

  it("removes a taxon when × is clicked", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676, 562]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByRole("button", { name: /report cart/i }));
    await userEvent.click(screen.getByLabelText("Remove HIV-1 from report"));
    expect(screen.queryByText("HIV-1")).not.toBeInTheDocument();
    expect(screen.getByRole("dialog")).toHaveTextContent("1 taxon in report");
  });

  it("clearing all hides the cart entirely", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676, 562]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByRole("button", { name: /report cart/i }));
    await userEvent.click(screen.getByRole("button", { name: /clear all/i }));
    expect(screen.queryByRole("button", { name: /report cart/i })).not.toBeInTheDocument();
  });

  it("closes the popover on Escape", async () => {
    render(
      <Wrapper>
        <Seeder taxonIds={[11676]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByRole("button", { name: /report cart/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    // Pill itself stays — it's still in the document.
    expect(screen.getByRole("button", { name: /report cart/i })).toBeInTheDocument();
  });

  it("closes the popover when clicking outside it", async () => {
    render(
      <Wrapper>
        <div data-testid="outside" style={{ height: 50 }}>
          outside content
        </div>
        <Seeder taxonIds={[11676]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={lookup} />
      </Wrapper>
    );
    await userEvent.click(screen.getByTestId("seed"));
    await userEvent.click(screen.getByRole("button", { name: /report cart/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("outside"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("falls back to a placeholder when a taxon is not in the lookup", async () => {
    const partial = new Map<number, CartTaxonInfo>();
    render(
      <Wrapper>
        <Seeder taxonIds={[99999]} />
        <ReportCart sampleId={SAMPLE_ID} taxonLookup={partial} />
      </Wrapper>
    );
    await act(async () => {
      await userEvent.click(screen.getByTestId("seed"));
    });
    await userEvent.click(screen.getByRole("button", { name: /report cart/i }));
    expect(screen.getByText("Taxon 99999")).toBeInTheDocument();
  });
});
