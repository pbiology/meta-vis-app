import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { getOutbreaks } from '../api/alerts'


export default function Alerts() {
  const navigate  = useNavigate()
  const [data,        setData]        = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [windowDays,  setWindowDays]  = useState(14)
  const location = useLocation()
  const [highlightedId, setHighlightedId] = useState(null)
  const sectionRefs = useRef({})

  useEffect(() => {
    setLoading(true)
    getOutbreaks(windowDays)
      .then(setData)
      .catch(() => setError('Failed to load outbreak alerts.'))
      .finally(() => setLoading(false))
  }, [windowDays])

  useEffect(() => {
    if (!data || !location.hash) return
    const taxonId = parseInt(location.hash.replace('#taxon-', ''))
    if (!taxonId) return
    setHighlightedId(taxonId)
    setTimeout(() => {
      const el = sectionRefs.current[taxonId]
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 100)
  }, [data, location.hash])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Outbreak alerts</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Window</span>
          {[7, 14, 30].map(d => (
            <button
              key={d}
              onClick={() => setWindowDays(d)}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                windowDays === d
                  ? 'bg-gray-900 text-white font-medium'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">Loading…</div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">{error}</div>
        )}
        {!loading && !error && data?.outbreaks.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 gap-2">
            <svg className="w-8 h-8 text-green-300" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 12l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <p className="text-sm text-gray-400">No outbreak signals detected in the last {windowDays} days.</p>
          </div>
        )}
        {!loading && !error && data?.outbreaks.map(outbreak => (
          <section
            key={outbreak.taxon_id}
            id={`taxon-${outbreak.taxon_id}`}
            ref={el => sectionRefs.current[outbreak.taxon_id] = el}
            className={`bg-white border rounded-xl transition-colors duration-500 ${
              highlightedId === outbreak.taxon_id
                ? 'border-amber-400 ring-2 ring-amber-200'
                : 'border-amber-100'
            }`}
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-amber-50">
              <svg className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" viewBox="0 0 16 16" fill="none">
                <path d="M8 2L14 13H2L8 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
                <path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
              <p className="text-xs font-medium text-gray-700 italic flex-1">{outbreak.taxon_name.replace(/-/g, ' ')}</p>
              <span className="text-xs text-amber-600 font-medium">
                {outbreak.case_ids.length} cases · {windowDays}d window
              </span>
            </div>
            <table className="w-full text-left border-collapse">
              <thead>
                <tr>
                  {['Case', 'Order date'].map(h => (
                    <th key={h} className="px-4 py-2 text-xs font-medium text-gray-400 border-b border-gray-50">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {outbreak.cases
                  .sort((a, b) => (a.order_date ?? '').localeCompare(b.order_date ?? ''))
                  .map(c => (
                    <tr
                      key={c.case_id}
                      onClick={() => navigate(`/cases/${c.case_name}`)}
                      className="cursor-pointer border-b border-gray-50 hover:bg-amber-50 transition-colors"
                    >
                      <td className="px-4 py-2.5 font-mono text-xs text-gray-700">{c.case_name}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-500">{c.order_date ?? '—'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  )
}