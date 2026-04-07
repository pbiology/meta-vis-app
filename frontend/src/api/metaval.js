import client from './client'

export async function getMetavalForSample(sampleId) {
  const res = await client.get(`/metaval/sample/${sampleId}`)
  return res.data
}

export async function getMetavalResult(metavalId) {
  const res = await client.get(`/metaval/${metavalId}`)
  return res.data
}

export function getReadsDownloadUrl(metavalId, readNum) {
  // Returns a direct URL the browser can use for download / fetch.
  // client.defaults.baseURL already contains the API origin.
  const base = client.defaults.baseURL ?? ''
  return `${base}/metaval/${metavalId}/reads/${readNum}`
}

export async function submitBlast(metavalId, readNum) {
  const res = await client.post(`/metaval/${metavalId}/blast/${readNum}`)
  return res.data
}

export async function getIgvUrl(metavalId, organismName) {
  const res = await client.get(
    `/metaval/${metavalId}/igv/${encodeURIComponent(organismName)}`,
    { responseType: 'blob' }
  )
  return URL.createObjectURL(res.data)
}