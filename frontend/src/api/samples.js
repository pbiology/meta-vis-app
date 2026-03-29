import client from './client'

export async function getSamples() {
  // Fetch all runs first, then samples for each run
  const runsRes = await client.get('/runs')
  const runs = runsRes.data

  const allSamples = []
  await Promise.all(
    runs.map(async (run) => {
      const samplesRes = await client.get(`/runs/${run.run_id}/samples`)
      samplesRes.data.forEach((s) => {
        allSamples.push({ ...s, run_id_str: run.run_id })
      })
    })
  )

  // Sort by order_date desc, then ingested_at desc
  allSamples.sort((a, b) => {
    const dateA = a.order_date || a.ingested_at
    const dateB = b.order_date || b.ingested_at
    return dateB.localeCompare(dateA)
  })

  return allSamples
}

export async function getSample(sampleId) {
  const res = await client.get(`/samples/${sampleId}`)
  return res.data
}

export async function getProfile(sampleId) {
  const res = await client.get(`/samples/${sampleId}/profile`)
  return res.data
}

export async function reviewSample(sampleId, notes = null) {
  const res = await client.patch(`/samples/${sampleId}/review`, { notes })
  return res.data
}

export async function getRunControls(runId) {
  const res = await client.get(`/runs/${runId}/samples`, {
    params: { type: 'controls' },
  })
  return res.data
}

export async function getKronaUrl(sampleId) {
  const resp = await client.get(`/api/v1/samples/${sampleId}/krona`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(resp.data)
}