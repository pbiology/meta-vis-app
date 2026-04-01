import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSamples } from '../api/samples'
import Badge from '../components/Badge'

const FILTERS = ['All', 'Pending', 'Reviewed', 'Samples', 'Controls']

function fmt(n) {
  if (n === undefined || n === null) return '—'
  return n.toLocaleString()
}

function fmtPct(n) {
  if (n === undefined || n === null) return '—'
  return `${n.toFixed(1)}%`
}

export default function SampleList() {
  const [samples, setSamples] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All')
  const navigate = useNavigate()

  useEffect(() => {
    getSamples()
      .then(setSamples)
      .catch(() => setError('Failed to load samples.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    let list = samples

    if (filter === 'Pending')  list = list.filter(s => !s.case_review?.reviewed)
    if (filter === 'Reviewed') list = list.filter(s =>  s.case_review?.reviewed)
    if (filter === 'Samples')     list = list.filter(s => s.sample_type === 'sample')
    if (filter === 'Controls') list = list.filter(s =>
      s.sample_type === 'negative_ctrl' || s.sample_type === 'positive_ctrl'
    )

    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(s =>
        s.sample?.sample_id?.toLowerCase().includes(q) ||
        s.subject_id?.toLowerCase().includes(q) ||
        s.case_id?.toLowerCase().includes(q)
      )
    }

    return list
  }, [samples, filter, search])

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">All samples</h1>
        <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 w-56">
          <svg className="w-3 h-3 text-gray-400 flex-shrink-0" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input
            type="text"
            placeholder="Search subject, sample ID…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-transparent text-xs text-gray-700 placeholder-gray-400 outline-none w-full"
          />
        </div>
      </div>

      {/* Filter chips */}
      <div className="flex gap-2 px-6 py-3 bg-white border-b border-gray-100">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs transition-colors ${
              filter === f
                ? 'bg-gray-900 text-white font-medium'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-400 self-center">
          {filtered.length} sample{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">
            {error}
          </div>
        )}
        {!loading && !error && (
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr>
                {['Sample ID', 'Subject', 'Order date', 'Case', 'Type', 'Unclassified', 'Species', 'Case status'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => {
                const reviewed = s.case_review?.reviewed
                return (
                  <tr
                    key={s._id}
                    onClick={() => navigate(`/samples/${s._id}`)}
                    className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-700">
                      {s.sample?.sample_id ?? '—'}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">
                      {s.subject_id ? s.subject_id.slice(-6) : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {s.order_date ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                      {s.case_id ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge type={s.sample_type} />
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {fmtPct(s.taxprofiler?.classifiers?.kraken2?.pct_unclassified)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {fmt(s.taxprofiler?.classifiers?.kraken2?.num_species)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge type={reviewed ? 'reviewed' : 'pending'} />
                    </td>
                  </tr>
                )
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-gray-400">
                    No samples match this filter.
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