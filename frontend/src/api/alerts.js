import client from './client'

export async function getOutbreaks(windowDays = 14) {
  const res = await client.get('/alerts/outbreaks', { params: { window_days: windowDays } })
  return res.data
}

export async function getIgnorelist() {
  const res = await client.get('/alerts/ignorelist')
  return res.data
}

export async function addToIgnorelist(taxonId, taxonName, reason = null) {
  const res = await client.post('/alerts/ignorelist', { taxon_id: taxonId, taxon_name: taxonName, reason })
  return res.data
}

export async function removeFromIgnorelist(taxonId) {
  const res = await client.delete(`/alerts/ignorelist/${taxonId}`)
  return res.data
}

export async function updateIgnorelistNote(taxonId, reason) {
  const res = await client.patch(`/alerts/ignorelist/${taxonId}`, { reason })
  return res.data
}