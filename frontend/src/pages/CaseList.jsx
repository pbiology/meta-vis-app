import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCases, getCaseSamples } from '../api/cases'
import Badge from '../components/Badge'

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
        const casesData = await getCases()
        const enriched = await Promise.all(
          casesData.map(async c => {
            const samples = await getCaseSamples(c.case_id)
            const testSamples = samples.filter(s => s.sample_type === 'test')
            return { ...c, samples, testSamples, date: earliestOrderDate(samples) }
          })
        )
        const sorted = enriched.sort((a, b) => {
          // Pending before reviewed
          const aReviewed = a.review?.reviewed ? 1 : 0
          const bReviewed = b.review?.reviewed ? 1 : 0
          if (aReviewed !== bReviewed) return aReviewed - bReviewed
          // Then by date descending within each group
          const aDate = a.date ?? a.ingested_at ?? ''
          const bDate = b.date ?? b.ingested_at ?? ''
          return bDate.localeCompare(aDate)
        })
        setCases(sorted)
      } catch {
        setError('Failed to load cases.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const pending  = cases.filter(c => !c.review?.reviewed).length
  const reviewed = cases.filter(c =>  c.review?.reviewed).length

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
                {['Case name', 'Date', 'Samples', 'Sample names', 'Notes', 'Status', 'Reviewed by'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cases.map(c => {
                const sampleNames = c.testSamples.map(s => s.sample?.sample_id).filter(Boolean)

                return (
                  <tr
                    key={c._id}
                    onClick={() => navigate(`/cases/${c.case_id}`)}
                    className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-700">{c.case_id}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{c.date ?? '—'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {c.testSamples.length} test{c.testSamples.length !== 1 ? 's' : ''}
                      {c.samples.length > c.testSamples.length && (
                        <span className="text-gray-300 ml-1">+{c.samples.length - c.testSamples.length} ctrl</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600" style={{ maxWidth: '220px' }}>
                      <span
                        className="block truncate"
                        title={sampleNames.join(', ')}
                      >
                        {sampleNames.join(', ') || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {(c.notes?.length ?? 0) > 0
                        ? <span className="text-amber-600 font-medium">{c.notes.length}</span>
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge type={c.review?.reviewed ? 'reviewed' : 'pending'} />
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {c.review?.reviewed_by ?? '—'}
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