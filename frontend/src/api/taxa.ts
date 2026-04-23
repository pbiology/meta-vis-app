import client from "./client";
import type {
  BvbrcGenomesResponse,
  BvbrcSpecialtyGenesResponse,
  Taxon,
  TaxonExternalLinks,
  TaxonLiterature,
  TaxonOccurrences,
} from "./types";

export type TaxonId = number | string;

export async function getTaxon(taxonId: TaxonId): Promise<Taxon> {
  const res = await client.get<Taxon>(`/taxa/${taxonId}`);
  return res.data;
}

export async function getTaxonOccurrences(
  taxonId: TaxonId,
  windowDays = 90
): Promise<TaxonOccurrences> {
  const res = await client.get<TaxonOccurrences>(`/taxa/${taxonId}/occurrences`, {
    params: { window_days: windowDays },
  });
  return res.data;
}

export async function updateClinicalNotes(
  taxonId: TaxonId,
  clinicalNotes: string | null
): Promise<Taxon> {
  const res = await client.patch<Taxon>(`/taxa/${taxonId}/clinical_notes`, {
    clinical_notes: clinicalNotes,
  });
  return res.data;
}

export async function getTaxonExternalLinks(taxonId: TaxonId): Promise<TaxonExternalLinks> {
  const res = await client.get<TaxonExternalLinks>(`/taxa/${taxonId}/external_links`);
  return res.data;
}

export async function getTaxonLiterature(
  taxonId: TaxonId,
  maxResults = 5
): Promise<TaxonLiterature> {
  const res = await client.get<TaxonLiterature>(`/taxa/${taxonId}/literature`, {
    params: { max_results: maxResults },
  });
  return res.data;
}

export async function getBvbrcGenomes(taxonId: TaxonId): Promise<BvbrcGenomesResponse> {
  const res = await client.get<BvbrcGenomesResponse>(`/taxa/${taxonId}/bvbrc/genomes`);
  return res.data;
}

export async function getBvbrcSpecialtyGenes(
  taxonId: TaxonId
): Promise<BvbrcSpecialtyGenesResponse> {
  const res = await client.get<BvbrcSpecialtyGenesResponse>(
    `/taxa/${taxonId}/bvbrc/specialty_genes`
  );
  return res.data;
}
