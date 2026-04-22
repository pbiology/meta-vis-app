import client from "./client";

export async function getMetavalForSample(sampleId: string): Promise<unknown> {
  const res = await client.get(`/metaval/sample/${sampleId}`);
  return res.data;
}

export async function getMetavalResult(metavalId: string): Promise<unknown> {
  const res = await client.get(`/metaval/${metavalId}`);
  return res.data;
}

export async function submitBlast(metavalId: string): Promise<unknown> {
  const res = await client.post(`/metaval/${metavalId}/blast`);
  return res.data;
}

export async function getIgvUrl(metavalId: string, organismName: string): Promise<string> {
  const res = await client.get<Blob>(
    `/metaval/${metavalId}/igv/${encodeURIComponent(organismName)}`,
    {
      responseType: "blob",
    }
  );
  return URL.createObjectURL(res.data);
}
