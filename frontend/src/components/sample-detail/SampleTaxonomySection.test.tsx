import { describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SampleTaxonomySection from "./SampleTaxonomySection";
import { renderWithProviders } from "../../test/utils";
import { metavalSummary, taxprofilerProfile } from "../../test/fixtures/samples";
import type { MetavalSummary } from "../../api/types";

const ALL_KINGDOMS = { "taxonomy-filters": { kingdoms: [] } };

function renderSection(
  overrides: {
    metavalResults?: MetavalSummary[];
    hasMetavalAnalysis?: boolean;
    metavalLoadFailed?: boolean;
    isTrana?: boolean;
    onSelectMetaval?: (id: string) => void;
  } = {}
) {
  const profile = taxprofilerProfile();
  return renderWithProviders(
    <SampleTaxonomySection
      classifiers={[profile]}
      qc={undefined}
      metavalResults={overrides.metavalResults ?? []}
      hasMetavalAnalysis={overrides.hasMetavalAnalysis ?? true}
      metavalLoadFailed={overrides.metavalLoadFailed ?? false}
      sampleId="sample-1"
      outbreakTaxonIds={new Set()}
      ntcProfiles={[]}
      contaminantConfig={null}
      pathogenIds={new Set()}
      isTrana={overrides.isTrana ?? false}
      sampleType="sample"
      activeTab="kraken2"
      onTabChange={() => {}}
      onSelectTaxon={() => {}}
      onSelectMetaval={overrides.onSelectMetaval ?? (() => {})}
    />,
    { sessionStorage: ALL_KINGDOMS }
  );
}

describe("SampleTaxonomySection — metaval status", () => {
  it("says metaval was not run", () => {
    renderSection({ hasMetavalAnalysis: false });
    expect(screen.getByText("Metaval: not run for this analysis.")).toBeInTheDocument();
  });

  it("says metaval ran but examined nothing for this classifier", () => {
    renderSection({ metavalResults: [metavalSummary({ classifier: "centrifuge" })] });
    expect(screen.getByText("Metaval: no taxa examined for kraken2.")).toBeInTheDocument();
  });

  it("counts the taxa examined for the active classifier", () => {
    renderSection({
      metavalResults: [
        metavalSummary(),
        metavalSummary({ _id: "mv-ecoli", taxon_id: 562, taxon_name: "Escherichia-coli" }),
      ],
    });
    expect(screen.getByText("Metaval: 2 taxa examined for kraken2.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows nothing when metaval failed to load — the caller warns instead", () => {
    renderSection({ metavalLoadFailed: true });
    expect(screen.queryByText(/^Metaval:/)).not.toBeInTheDocument();
  });

  it("shows nothing for TRANA samples", () => {
    renderSection({ isTrana: true });
    expect(screen.queryByText(/^Metaval:/)).not.toBeInTheDocument();
  });

  it("lists results without a table row and opens them", async () => {
    const onSelectMetaval = vi.fn();
    renderSection({
      onSelectMetaval,
      metavalResults: [
        metavalSummary(),
        // Unresolved taxon (old-format metaval output).
        metavalSummary({ _id: "mv-old", taxon_id: null, display_name: "Old virus" }),
        // Host taxon: in the profile, but never listed in the table.
        metavalSummary({ _id: "mv-host", taxon_id: 9606, display_name: "Homo sapiens" }),
      ],
    });

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("2 metaval results have no row in the kraken2 table:");
    await userEvent.click(within(alert).getByRole("button", { name: "Old virus" }));
    expect(onSelectMetaval).toHaveBeenCalledWith("mv-old");
    expect(within(alert).getByRole("button", { name: "Homo sapiens" })).toBeInTheDocument();
  });
});
