import client from "./client";
import type { Taxon } from "./types";

export type TaxonId = number | string;

export async function getTaxon(taxonId: TaxonId): Promise<Taxon> {
  const res = await client.get<Taxon>(`/taxa/${taxonId}`);
  return res.data;
}

export async function getTaxonOccurrences(taxonId: TaxonId, windowDays = 90): Promise<unknown> {
  const res = await client.get(`/taxa/${taxonId}/occurrences`, {
    params: { window_days: windowDays },
  });
  return res.data;
}

export async function updateClinicalNotes(
  taxonId: TaxonId,
  clinicalNotes: string
): Promise<unknown> {
  const res = await client.patch(`/taxa/${taxonId}/clinical_notes`, {
    clinical_notes: clinicalNotes,
  });
  return res.data;
}

export async function getTaxonExternalLinks(taxonId: TaxonId): Promise<unknown> {
  const res = await client.get(`/taxa/${taxonId}/external_links`);
  return res.data;
}

export async function getTaxonLiterature(taxonId: TaxonId, maxResults = 5): Promise<unknown> {
  const res = await client.get(`/taxa/${taxonId}/literature`, {
    params: { max_results: maxResults },
  });
  return res.data;
}

export async function getBvbrcGenomes(taxonId: TaxonId): Promise<unknown> {
  const res = await client.get(`/taxa/${taxonId}/bvbrc/genomes`);
  return res.data;
}

export async function getBvbrcSpecialtyGenes(taxonId: TaxonId): Promise<unknown> {
  const res = await client.get(`/taxa/${taxonId}/bvbrc/specialty_genes`);
  return res.data;
}
