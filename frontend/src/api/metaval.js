import client from './client'

export async function getMetavalForSample(sampleId) {
  const res = await client.get(`/metaval/sample/${sampleId}`)
  return res.data
}

export async function getMetavalResult(metavalId) {
  const res = await client.get(`/metaval/${metavalId}`)
  return res.data
}

export async function getIgvUrl(metavalId, organismName) {
  const res = await client.get(
    `/metaval/${metavalId}/igv/${encodeURIComponent(organismName)}`,
    { responseType: 'blob' }
  )
  return URL.createObjectURL(res.data)
}