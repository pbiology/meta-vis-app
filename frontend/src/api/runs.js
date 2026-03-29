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