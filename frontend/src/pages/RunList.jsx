import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRuns, getRunSamples } from '../api/runs'

function earliestOrderDate(samples) {
  const dates = samples
    .map(s => s.order_date)
    .filter(Boolean)
    .sort()
  return dates.length > 0 ? dates[0] : null
}

export default function RunList() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      try {
        const runsData = await getRuns()
        // Fetch samples for each run to get order_date
        const enriched = await Promise.all(
          runsData.map(async run => {
            const samples = await getRunSamples(run.run_id)
            return {
              ...run,
              samples,
              date: earliestOrderDate(samples),
            }
          })
        )
        setRuns(enriched)
      } catch {
        setError('Failed to load runs.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Runs</h1>
        <span className="text-xs text-gray-400">{runs.length} run{runs.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="flex-1 overflow-auto">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">Loading…</div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">{error}</div>
        )}
        {!loading && !error && (
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr>
                {['Run ID', 'Date', 'Samples'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr
                  key={run._id}
                  onClick={() => navigate(`/runs/${run.run_id}`)}
                  className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{run.run_id}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{run.date ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-700">{run.samples.length}</td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-10 text-center text-sm text-gray-400">
                    No runs found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}