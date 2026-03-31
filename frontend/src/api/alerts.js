import client from './client'

export async function getOutbreaks(windowDays = 14) {
  const res = await client.get('/alerts/outbreaks', { params: { window_days: windowDays } })
  return res.data
}