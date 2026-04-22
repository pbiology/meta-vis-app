import client from "./client";

export async function getTaxon(taxonId) {
  const res = await client.get(`/taxa/${taxonId}`);
  return res.data;
}

export async function getTaxonOccurrences(taxonId, windowDays = 90) {
  const res = await client.get(`/taxa/${taxonId}/occurrences`, {
    params: { window_days: windowDays },
  });
  return res.data;
}

export async function updateClinicalNotes(taxonId, clinicalNotes) {
  const res = await client.patch(`/taxa/${taxonId}/clinical_notes`, {
    clinical_notes: clinicalNotes,
  });
  return res.data;
}

export async function getTaxonExternalLinks(taxonId) {
  const res = await client.get(`/taxa/${taxonId}/external_links`);
  return res.data;
}

export async function getTaxonLiterature(taxonId, maxResults = 5) {
  const res = await client.get(`/taxa/${taxonId}/literature`, {
    params: { max_results: maxResults },
  });
  return res.data;
}

export async function getBvbrcGenomes(taxonId) {
  const res = await client.get(`/taxa/${taxonId}/bvbrc/genomes`);
  return res.data;
}

export async function getBvbrcSpecialtyGenes(taxonId) {
  const res = await client.get(`/taxa/${taxonId}/bvbrc/specialty_genes`);
  return res.data;
}
