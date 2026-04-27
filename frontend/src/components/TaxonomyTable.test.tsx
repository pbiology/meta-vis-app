import { describe, it, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import TaxonomyTable from "./TaxonomyTable";
import { renderWithProviders } from "../test/utils";
import { taxprofilerProfile, tranaProfile } from "../test/fixtures/samples";

const baseProps = {
  sampleId: "sample-1",
  outbreakTaxonIds: new Set<number>(),
  ntcProfiles: [],
  metavalResults: [],
};

function nonHostBodyRows() {
  // First table is the taxonomy table; rows include header so we filter to tbody.
  const table = screen.getByRole("table");
  return within(table).getAllByRole("row").slice(1);
}

// Auth context defaults sessionKingdoms to ["Viruses"], which TaxonomyTable
// uses as the initial kingdom filter. Most tests want all kingdoms visible
// so they can assert pre-filter behaviour — so we seed an empty kingdoms list.
const ALL_KINGDOMS = { "taxonomy-filters": { kingdoms: [] } };

describe("TaxonomyTable — bug regression coverage", () => {
  it("does not narrow results when metavalOnly is set in sessionStorage but no metaval results exist", () => {
    // Reproduces the trana bug: stale sessionStorage flag + hidden control = empty table.
    const profile = tranaProfile();
    renderWithProviders(
      <TaxonomyTable
        {...baseProps}
        profile={profile}
        allProfiles={[profile]}
        abundanceIsFraction
      />,
      { sessionStorage: { "taxonomy-filters": { kingdoms: [], metavalOnly: true } } }
    );

    // 3 non-host rows (Homo sapiens filtered out).
    expect(nonHostBodyRows()).toHaveLength(3);
    expect(screen.queryByText(/no organisms match your filters/i)).not.toBeInTheDocument();
  });

  it("hides the 'Metaval only' toggle when there are no metaval results", () => {
    renderWithProviders(
      <TaxonomyTable {...baseProps} profile={tranaProfile()} abundanceIsFraction />,
      { sessionStorage: ALL_KINGDOMS }
    );
    expect(screen.queryByRole("button", { name: /metaval only/i })).not.toBeInTheDocument();
  });

  it("renders all non-host taxprofiler rows by default (mixed kingdoms)", () => {
    const profile = taxprofilerProfile();
    renderWithProviders(
      <TaxonomyTable {...baseProps} profile={profile} allProfiles={[profile]} />,
      { sessionStorage: ALL_KINGDOMS }
    );
    // All non-host taxa: 562, 1392, 11676, 4932 → 4 rows.
    expect(nonHostBodyRows()).toHaveLength(4);
    expect(screen.getByText("Escherichia coli")).toBeInTheDocument();
    expect(screen.getByText("HIV-1")).toBeInTheDocument();
  });

  it("hidden-control invariant: persisted filters must not narrow results when their toggle is hidden", () => {
    // Parametrize over each persisted filter key. For every one, if its UI control
    // is not rendered (because the input data doesn't enable it), the filter must
    // be a no-op. Catches the bug class generically.
    const profile = tranaProfile();
    const cases: Array<{ name: string; persisted: Record<string, unknown> }> = [
      { name: "metavalOnly with no metaval", persisted: { kingdoms: [], metavalOnly: true } },
      // taxSearch and concordanceMin controls are always visible — they're allowed
      // to narrow results — so we don't include them here. Add new filter keys to
      // this list whenever a new conditionally-rendered filter is introduced.
    ];

    for (const { name, persisted } of cases) {
      sessionStorage.clear();
      const { unmount } = renderWithProviders(
        <TaxonomyTable
          {...baseProps}
          profile={profile}
          allProfiles={[profile]}
          abundanceIsFraction
        />,
        { sessionStorage: { "taxonomy-filters": persisted } }
      );
      expect(nonHostBodyRows().length, `case: ${name}`).toBeGreaterThan(0);
      unmount();
    }
  });
});
