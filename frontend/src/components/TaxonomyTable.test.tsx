import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TaxonomyTable from "./TaxonomyTable";
import { renderWithProviders } from "../test/utils";
import { entry, taxprofilerProfile, tranaProfile } from "../test/fixtures/samples";
import type { SampleProfile } from "../api/types";

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

describe("TaxonomyTable — report selection", () => {
  it("renders no checkbox column when selection prop is omitted", () => {
    const profile = taxprofilerProfile();
    renderWithProviders(
      <TaxonomyTable {...baseProps} profile={profile} allProfiles={[profile]} />,
      { sessionStorage: ALL_KINGDOMS }
    );
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("renders checkboxes and calls onToggle when a row is clicked", async () => {
    const profile = taxprofilerProfile();
    const onToggle = vi.fn();
    renderWithProviders(
      <TaxonomyTable
        {...baseProps}
        profile={profile}
        allProfiles={[profile]}
        selection={{ selected: new Set([562]), onToggle }}
      />,
      { sessionStorage: ALL_KINGDOMS }
    );

    // E. coli row is pre-selected per the prop.
    const ecoliRow = screen.getByText("Escherichia coli").closest("tr")!;
    const ecoliCheckbox = within(ecoliRow).getByRole("checkbox");
    expect(ecoliCheckbox).toBeChecked();

    // HIV-1 row is not selected; clicking should fire onToggle with its taxon_id.
    const hivRow = screen.getByText("HIV-1").closest("tr")!;
    const hivCheckbox = within(hivRow).getByRole("checkbox");
    expect(hivCheckbox).not.toBeChecked();
    await userEvent.click(hivCheckbox);
    expect(onToggle).toHaveBeenCalledWith(11676);
  });
});

describe("TaxonomyTable — read totals", () => {
  // Kraken2 via taxpasta reports DIRECT counts, so root holds only the reads
  // that could not be placed deeper: it is far smaller than the host row and
  // smaller than a single family. Proportions follow a production run.
  function directCountProfile(): SampleProfile {
    return {
      classifier: "kraken2",
      classifier_db: "k2_pluspf",
      profile: [
        entry(0, "unclassified", null, 1_000_000),
        entry(1, "root", null, 2_700_000, "no rank"),
        entry(131567, "cellular organisms", null, 50_000, "no rank"),
        entry(543, "Enterobacteriaceae", "Bacteria", 4_350_000, "family"),
        entry(9606, "Homo sapiens", "Eukaryota", 17_500_000),
        entry(11676, "HIV-1", "Viruses", 250),
      ],
    };
  }

  function cardValue(label: string) {
    return screen.getByText(label).parentElement?.querySelector("p:last-child")?.textContent;
  }

  it("derives the totals from direct counts, not from the root row", () => {
    renderWithProviders(<TaxonomyTable {...baseProps} profile={directCountProfile()} />, {
      sessionStorage: ALL_KINGDOMS,
    });

    // Every row except unclassified: 24,600,250 — not root's 2,700,000.
    expect(cardValue("Total classified")).toBe((24_600_250).toLocaleString());
    // Minus direct host reads. Using root made this negative.
    expect(cardValue("Non-host reads")).toBe((7_100_250).toLocaleString());
  });

  it("uses the corrected denominator for row percentages", () => {
    renderWithProviders(<TaxonomyTable {...baseProps} profile={directCountProfile()} />, {
      sessionStorage: ALL_KINGDOMS,
    });

    // 4,350,000 / 7,100,250. The root fallback left the denominator negative,
    // so every row rendered as 0.000%.
    const familyRow = screen.getByText("Enterobacteriaceae").closest("tr")!;
    expect(within(familyRow).getByText("61.265%")).toBeInTheDocument();
    const hivRow = screen.getByText("HIV-1").closest("tr")!;
    expect(within(hivRow).getByText("0.004%")).toBeInTheDocument();
  });

  it("prefers the classified total from QC when it is present", () => {
    renderWithProviders(
      <TaxonomyTable
        {...baseProps}
        profile={directCountProfile()}
        clfQc={{ classified_reads: 38_734_323 }}
      />,
      { sessionStorage: ALL_KINGDOMS }
    );

    expect(cardValue("Total classified")).toBe((38_734_323).toLocaleString());
    expect(cardValue("Non-host reads")).toBe((21_234_323).toLocaleString());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("warns when QC contradicts the profile instead of showing a clamped total silently", () => {
    renderWithProviders(
      <TaxonomyTable
        {...baseProps}
        profile={directCountProfile()}
        clfQc={{ classified_reads: 1000 }}
      />,
      { sessionStorage: ALL_KINGDOMS }
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/host reads exceed the classified total/i);
    expect(cardValue("Non-host reads")).toBe("0");
  });

  it("shows no read counts for relative-abundance profiles", () => {
    // TRANA/Emu profiles are fractions; rounding them to reads printed "1".
    renderWithProviders(
      <TaxonomyTable {...baseProps} profile={tranaProfile()} abundanceIsFraction />,
      { sessionStorage: ALL_KINGDOMS }
    );

    expect(cardValue("Total classified")).toBe("—");
    expect(cardValue("Non-host reads")).toBe("—");
  });
});
