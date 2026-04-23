import type { NcbiEsummaryResponse, NcbiTaxonResult } from "../api/types";

function superkingdomFromLineage(lineage = ""): string | null {
  for (const sk of ["Viruses", "Bacteria", "Eukaryota", "Archaea"]) {
    if (lineage.includes(sk)) return sk;
  }
  return null;
}

// Cellular organisms (Bacteria, Archaea, Eukaryota) have a populated lineage
// string in NCBI esummary, which includes the kingdom name directly.
// Viruses have an empty lineage because they sit outside the cellular organism
// hierarchy — instead, NCBI always populates genbankdivision for them.
const GENBANK_DIVISION_TO_KINGDOM: Record<string, string> = {
  Viruses: "Viruses",
  Phages: "Viruses",
  Bacteria: "Bacteria",
  Archaea: "Archaea",
  Mammals: "Eukaryota",
  Primates: "Eukaryota",
  Rodents: "Eukaryota",
  Vertebrates: "Eukaryota",
  Invertebrates: "Eukaryota",
  Plants: "Eukaryota",
  Fungi: "Eukaryota",
};

export interface LookupTaxonResult {
  name: string;
  superkingdom: string | null;
}

export async function lookupTaxon(taxonId: number): Promise<LookupTaxonResult> {
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&id=${taxonId}&retmode=json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("NCBI request failed");
  const data = (await res.json()) as NcbiEsummaryResponse;
  const raw = data.result?.[String(taxonId)];
  if (!raw || Array.isArray(raw)) throw new Error("Taxon not found");
  const result = raw as NcbiTaxonResult;
  if (result.status === "error") throw new Error("Taxon not found");
  const superkingdom =
    superkingdomFromLineage(result.lineage ?? "") ??
    (result.genbankdivision ? GENBANK_DIVISION_TO_KINGDOM[result.genbankdivision] : undefined) ??
    null;
  return { name: result.scientificname, superkingdom };
}
