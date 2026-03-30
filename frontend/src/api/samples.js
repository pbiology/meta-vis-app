import client from './client'

export async function getSamples() {
  // Fetch all cases first, then samples for each case
  const casesRes = await client.get('/cases')
  const cases = casesRes.data

  const allSamples = []
  await Promise.all(
    cases.map(async (c) => {
      const samplesRes = await client.get(`/cases/${c.case_id}/samples`)
      samplesRes.data.forEach((s) => {
        allSamples.push({ ...s, case_id: c.case_id, case_review: c.review })
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

export async function getKronaUrl(sampleId) {
  const resp = await client.get(`/samples/${sampleId}/krona`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(resp.data)
}