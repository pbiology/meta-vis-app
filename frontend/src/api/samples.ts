import client from "./client";

export async function getSamples({ page = 1, search = "", filter = "", analysisType } = {}) {
  const params = { page, search, filter };
  if (analysisType) params.analysis_type = analysisType;
  const res = await client.get("/samples", { params });
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
