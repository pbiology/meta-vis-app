import type { MetavalSummary, SampleProfile, SampleProfileEntry } from "../../api/types";

export function entry(
  taxon_id: number,
  name: string,
  superkingdom: SampleProfileEntry["superkingdom"],
  abundance: number,
  rank: string = "species"
): SampleProfileEntry {
  return { taxon_id, name, superkingdom, abundance, rank };
}

// Mixed-kingdom taxprofiler-shaped profile.
export function taxprofilerProfile(classifier = "kraken2"): SampleProfile {
  return {
    classifier,
    classifier_db: "k2_pluspf",
    profile: [
      entry(9606, "Homo sapiens", "Eukaryota", 5_000_000),
      entry(0, "unclassified", null, 100_000),
      entry(1, "root", null, 0),
      entry(562, "Escherichia coli", "Bacteria", 4321),
      entry(1392, "Bacillus anthracis", "Bacteria", 32),
      entry(11676, "HIV-1", "Viruses", 11),
      entry(4932, "Saccharomyces cerevisiae", "Eukaryota", 7),
    ],
  };
}

// Trana-shaped profile (single classifier, viral hits, fractional-friendly).
export function tranaProfile(): SampleProfile {
  return {
    classifier: "emu",
    classifier_db: "emu_db",
    profile: [
      entry(9606, "Homo sapiens", "Eukaryota", 0.1),
      entry(11676, "HIV-1", "Viruses", 0.4),
      entry(11320, "Influenza A virus", "Viruses", 0.3),
      entry(562, "Escherichia coli", "Bacteria", 0.05),
    ],
  };
}

// One metaval list-endpoint entry; defaults to HIV-1 under kraken2, which has a
// row in taxprofilerProfile().
export function metavalSummary(overrides: Partial<MetavalSummary> = {}): MetavalSummary {
  return {
    _id: "mv-hiv",
    sample_id: "sample-1",
    classifier: "kraken2",
    taxon_id: 11676,
    taxon_name: "taxid_11676_HIV-1",
    display_name: "HIV 1",
    ...overrides,
  };
}
