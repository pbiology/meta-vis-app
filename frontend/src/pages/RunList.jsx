import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRuns, getRunSamples } from '../api/runs'
import Badge from '../components/Badge'

function fmt(n) {
  if (n === undefined || n === null) return '—'
  return n.toLocaleString()
}

function fmtPct(n) {
  if (n === undefined || n === null) return '—'
  return `${n.toFixed(1)}%`
}

function earliestOrderDate(samples) {
  const dates = samples.map(s => s.order_date).filter(Boolean).sort()
  return dates.length > 0 ? dates[0] : null
}

export default function CaseList() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      try {
        const runsData = await getRuns()
        const enriched = await Promise.all(
          runsData.map(async run => {
            const samples = await getRunSamples(run.run_id)
            const testSamples = samples.filter(s => s.sample_type === 'test')
            return { ...run, samples, testSamples, date: earliestOrderDate(samples) }
          })
        )
        setCases(enriched)
      } catch {
        setError('Failed to load cases.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const pending   = cases.filter(c => !c.review?.reviewed).length
  const reviewed  = cases.filter(c =>  c.review?.reviewed).length

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Cases</h1>
        <span className="text-xs text-gray-400 mr-2">
          <span className="text-amber-500 font-medium">{pending}</span> pending
        </span>
        <span className="text-xs text-gray-400">
          <span className="text-green-600 font-medium">{reviewed}</span> reviewed
        </span>
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
                {['Case ID', 'Date', 'Samples', 'Unclassified', 'Species', 'Status'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cases.map(c => {
                // Aggregate QC across test samples for the list view
                const k2vals = c.testSamples
                  .map(s => s.taxprofiler?.kraken2?.pct_unclassified)
                  .filter(v => v != null)
                const avgUnclassified = k2vals.length
                  ? k2vals.reduce((a, b) => a + b, 0) / k2vals.length
                  : null
                const totalSpecies = c.testSamples
                  .map(s => s.taxprofiler?.kraken2?.num_species)
                  .filter(v => v != null)
                  .reduce((a, b) => a + b, 0) || null

                return (
                  <tr
                    key={c._id}
                    onClick={() => navigate(`/cases/${c.run_id}`)}
                    className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-700">{c.run_id}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{c.date ?? '—'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {c.testSamples.length} test{c.testSamples.length !== 1 ? 's' : ''}
                      {c.samples.length > c.testSamples.length && (
                        <span className="text-gray-300 ml-1">+{c.samples.length - c.testSamples.length} ctrl</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {fmtPct(avgUnclassified)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">{fmt(totalSpecies)}</td>
                    <td className="px-4 py-3">
                      <Badge type={c.review?.reviewed ? 'reviewed' : 'pending'} />
                    </td>
                  </tr>
                )
              })}
              {cases.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-400">
                    No cases found.
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