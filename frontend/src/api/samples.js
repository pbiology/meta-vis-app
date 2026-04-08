import client from "./client";

export async function getSamples({ page = 1, search = "", filter = "" } = {}) {
  const res = await client.get("/samples", { params: { page, search, filter } });
  return res.data;
}

export async function getSample(sampleId) {
  const res = await client.get(`/samples/${sampleId}`);
  return res.data;
}

export async function getProfile(sampleId) {
  const res = await client.get(`/samples/${sampleId}/profile`);
  return res.data;
}

export async function getKronaUrl(sampleId, classifier = "kraken2") {
  const resp = await client.get(`/samples/${sampleId}/krona`, {
    params: { classifier },
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data);
}

export async function getNtcProfiles(sampleId) {
  const res = await client.get(`/samples/${sampleId}/ntc_profiles`);
  return res.data;
}
