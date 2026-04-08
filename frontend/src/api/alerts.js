import client from "./client";

export async function getOutbreaks(windowDays = 14) {
  const res = await client.get("/alerts/outbreaks", { params: { window_days: windowDays } });
  // Transform the new response format into a flat list of outbreaks
  // New API returns: { results: [{ config_name, outbreaks: [...] }, ...] }
  // Frontend expects: { outbreaks: [...] } for backward compatibility
  const data = res.data;
  if (data.results && Array.isArray(data.results)) {
    // Flatten all outbreaks from all configs into a single array
    const allOutbreaks = [];
    for (const configResult of data.results) {
      for (const outbreak of configResult.outbreaks || []) {
        allOutbreaks.push({
          ...outbreak,
          config_name: configResult.config_name,
          superkingdoms: configResult.superkingdoms,
        });
      }
    }
    return {
      window_days: data.window_days,
      outbreaks: allOutbreaks,
    };
  }
  // Fallback if response format is different
  return data;
}

export async function getIgnorelist(superkingdom = null) {
  const params = superkingdom ? { superkingdom } : {};
  const res = await client.get("/alerts/ignorelist", { params });
  return res.data;
}

export async function addToIgnorelist(taxonId, taxonName, superkingdom = "Viruses", reason = null) {
  const res = await client.post("/alerts/ignorelist", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    reason,
  });
  return res.data;
}

export async function removeFromIgnorelist(taxonId) {
  const res = await client.delete(`/alerts/ignorelist/${taxonId}`);
  return res.data;
}

export async function updateIgnorelistNote(taxonId, reason) {
  const res = await client.patch(`/alerts/ignorelist/${taxonId}`, { reason });
  return res.data;
}

export async function getPathogens() {
  const res = await client.get("/alerts/pathogens");
  return res.data;
}

export async function addToPathogens(taxonId, taxonName, superkingdom = "Viruses", notes = null) {
  const res = await client.post("/alerts/pathogens", {
    taxon_id: taxonId,
    taxon_name: taxonName,
    superkingdom,
    reason: notes,
  });
  return res.data;
}

export async function removeFromPathogens(taxonId) {
  const res = await client.delete(`/alerts/pathogens/${taxonId}`);
  return res.data;
}