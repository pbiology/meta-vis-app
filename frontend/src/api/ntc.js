import client from "./client";

export async function getNtcTrends({ material, windowDays = 90, minReads = 3, minCasePct = 0.1 }) {
  const res = await client.get("/ntc/trends", {
    params: {
      material,
      window_days: windowDays,
      min_reads: minReads,
      min_case_pct: minCasePct,
    },
  });
  return res.data;
}

// --- Ignorelist ---

export async function getNtcIgnorelist() {
  const res = await client.get("/ntc/ignorelist");
  return res.data;
}

export async function addToNtcIgnorelist(taxonId, taxonName, superkingdom, reason = null) {
  const res = await client.post("/ntc/ignorelist", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    reason,
  });
  return res.data;
}

export async function updateNtcIgnorelistNote(taxonId, reason) {
  const res = await client.patch(`/ntc/ignorelist/${taxonId}`, { reason });
  return res.data;
}

export async function removeFromNtcIgnorelist(taxonId) {
  const res = await client.delete(`/ntc/ignorelist/${taxonId}`);
  return res.data;
}

// --- Known contaminants ---

export async function getNtcContaminants() {
  const res = await client.get("/ntc/contaminants");
  return res.data;
}

export async function addNtcContaminant(
  taxonId,
  taxonName,
  superkingdom,
  minReads = 3,
  notes = null
) {
  const res = await client.post("/ntc/contaminants", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    min_reads: minReads,
    notes,
  });
  return res.data;
}

export async function updateNtcContaminant(taxonId, { minReads, notes }) {
  const res = await client.patch(`/ntc/contaminants/${taxonId}`, {
    min_reads: minReads,
    notes,
  });
  return res.data;
}

export async function removeNtcContaminant(taxonId) {
  const res = await client.delete(`/ntc/contaminants/${taxonId}`);
  return res.data;
}

// --- Contaminant alerts ---

export async function getNtcContaminantAlerts() {
  const res = await client.get("/ntc/contaminant-alerts");
  return res.data;
}

export async function getNtcContaminantCaseIds() {
  const res = await client.get("/ntc/contaminant-alerts");
  return { case_ids: res.data.contaminant_case_ids };
}
