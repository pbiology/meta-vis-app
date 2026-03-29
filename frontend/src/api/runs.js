import client from './client'

export async function getCases() {
  const res = await client.get('/cases')
  return res.data
}

export async function getCase(caseId) {
  const res = await client.get(`/cases/${caseId}`)
  return res.data
}

export async function getCaseSamples(caseId, type = null) {
  const params = type ? { type } : {}
  const res = await client.get(`/cases/${caseId}/samples`, { params })
  return res.data
}

export async function reviewCase(caseId, notes = null) {
  const res = await client.patch(`/cases/${caseId}/review`, { notes })
  return res.data
}

export async function getCaseKronaUrl(caseId) {
  const resp = await client.get(`/cases/${caseId}/krona`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(resp.data)
}