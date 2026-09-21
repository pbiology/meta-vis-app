import { describe, it, expect } from "vitest";
import { readTotals } from "./readTotals";
import { entry } from "../test/fixtures/samples";

// Shaped like real Kraken2 output via taxpasta: counts are DIRECT, so root
// holds only the reads that could not be placed deeper and a single family
// carries far more reads than root does. Proportions mirror the numbers seen
// in a production run (root 2.7M, host 17.5M, family 4.4M).
function directCountProfile() {
  return [
    entry(0, "unclassified", null, 1_000_000),
    entry(1, "root", null, 2_700_000),
    entry(131567, "cellular organisms", null, 50_000),
    entry(543, "Enterobacteriaceae", "Bacteria", 4_350_000),
    entry(9606, "Homo sapiens", "Eukaryota", 17_500_000),
    entry(11676, "HIV-1", "Viruses", 250),
  ];
}

describe("readTotals", () => {
  it("sums direct counts instead of reading the classified total off root", () => {
    const t = readTotals(directCountProfile());

    // Everything except taxon 0 — not root's 2,700,000.
    expect(t.classified).toBe(24_600_250);
    expect(t.unclassified).toBe(1_000_000);
    expect(t.total).toBe(25_600_250);
    // Classified minus direct host reads. The root fallback made this
    // negative (2.7M − 17.5M), which rendered as a negative read count.
    expect(t.nonHost).toBe(7_100_250);
    expect(t.hostExceedsClassified).toBe(false);
  });

  it("prefers the classified total from QC when it is present", () => {
    const t = readTotals(directCountProfile(), { classified_reads: 38_734_323 });

    expect(t.classified).toBe(38_734_323);
    expect(t.total).toBe(39_734_323);
    expect(t.nonHost).toBe(21_234_323);
  });

  it("counts 'unclassified <taxon>' rows as classified", () => {
    // These are real NCBI taxa holding placed reads; only taxon 0 is unplaced.
    const t = readTotals([
      entry(0, "unclassified", null, 10),
      entry(2323, "unclassified Bacteria", "Bacteria", 500),
    ]);

    expect(t.classified).toBe(500);
    expect(t.unclassified).toBe(10);
  });

  it("clamps nonHost at zero and flags QC that contradicts the profile", () => {
    // QC reports fewer classified reads than the profile assigns to host.
    const t = readTotals(directCountProfile(), { classified_reads: 1_000 });

    expect(t.nonHost).toBe(0);
    expect(t.hostExceedsClassified).toBe(true);
  });

  it("handles fraction profiles, which carry no unclassified row", () => {
    const t = readTotals([
      entry(9606, "Homo sapiens", "Eukaryota", 0.1),
      entry(11676, "HIV-1", "Viruses", 0.4),
      entry(562, "Escherichia coli", "Bacteria", 0.05),
    ]);

    expect(t.unclassified).toBe(0);
    expect(t.classified).toBeCloseTo(0.55);
    expect(t.nonHost).toBeCloseTo(0.45);
  });

  it("returns zeros for an empty profile without flagging it", () => {
    const t = readTotals([]);

    expect(t).toEqual({
      classified: 0,
      unclassified: 0,
      total: 0,
      nonHost: 0,
      hostExceedsClassified: false,
    });
  });
});
