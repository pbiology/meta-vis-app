import client from './client'

export async function getRuns() {
  const res = await client.get('/runs')
  return res.data
}

export async function getRun(runId) {
  const res = await client.get(`/runs/${runId}`)
  return res.data
}

export async function getRunSamples(runId, type = null) {
  const params = type ? { type } : {}
  const res = await client.get(`/runs/${runId}/samples`, { params })
  return res.data
}

export async function getRunKronaUrl(runObjectId) {
  // run_id here is the MongoDB ObjectId string from the sample document
  // We need to find the run_id string — use the runs endpoint
  const resp = await client.get(`/runs-by-oid/${runObjectId}/krona`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(resp.data)
}