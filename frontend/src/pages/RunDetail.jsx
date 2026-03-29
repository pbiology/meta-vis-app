import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getRunSamples } from '../api/runs'
import Badge from '../components/Badge'

function fmt(n) {
  if (n === undefined || n === null) return '—'
  return n.toLocaleString()
}

function fmtPct(n) {
  if (n === undefined || n === null) return '—'
  return `${n.toFixed(1)}%`
}

const FILTERS = ['All', 'Test', 'Controls']

export default function RunDetail() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const [samples, setSamples] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('All')

  useEffect(() => {
    getRunSamples(runId)
      .then(data => {
        // Attach run_id_str so SampleDetail can load controls
        setSamples(data.map(s => ({ ...s, run_id_str: runId })))
      })
      .catch(() => setError('Failed to load samples.'))
      .finally(() => setLoading(false))
  }, [runId])

  const filtered = useMemo(() => {
    if (filter === 'Test') return samples.filter(s => s.sample_type === 'test')
    if (filter === 'Controls') return samples.filter(s =>
      s.sample_type === 'negative_ctrl' || s.sample_type === 'positive_ctrl'
    )
    return samples
  }, [samples, filter])

  // Separate test samples and controls for the comparison table
  const testSamples = samples.filter(s => s.sample_type === 'test')
  const controls = samples.filter(s =>
    s.sample_type === 'negative_ctrl' || s.sample_type === 'positive_ctrl'
  )

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <button
          onClick={() => navigate('/runs')}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Runs
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 font-mono flex-1">{runId}</h1>
        <span className="text-xs text-gray-400">{samples.length} sample{samples.length !== 1 ? 's' : ''}</span>
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
      </div>

      <div className="flex-1 overflow-auto">
        {loading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">Loading…</div>
        )}
        {error && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">{error}</div>
        )}
        {!loading && !error && (
          <>
            {/* Samples table */}
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-white z-10">
                <tr>
                  {['Sample ID', 'Subject', 'Order date', 'Type', 'Unclassified', 'Species', 'Status'].map(h => (
                    <th key={h} className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(s => (
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
                    <td className="px-4 py-3 text-xs text-gray-500">{s.order_date ?? '—'}</td>
                    <td className="px-4 py-3"><Badge type={s.sample_type} /></td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {fmtPct(s.taxprofiler?.kraken2?.pct_unclassified)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {fmt(s.taxprofiler?.kraken2?.num_species)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge type={s.review?.reviewed ? 'reviewed' : 'pending'} />
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-400">
                      No samples match this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Controls comparison panel — only shown when controls exist */}
            {controls.length > 0 && (
              <div className="mx-6 my-4 bg-white border border-gray-100 rounded-xl p-4">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                  Controls comparison
                </p>
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="text-left text-xs font-medium text-gray-400 pb-2 pr-4">Metric</th>
                      {[...testSamples, ...controls].map(s => (
                        <th key={s._id} className="text-right text-xs font-medium text-gray-400 pb-2 px-3">
                          <span className="font-mono">{s.sample?.sample_id}</span>
                          <span className="block font-normal text-gray-300 normal-case">
                            {s.sample_type === 'test' ? 'test' : s.sample_type === 'negative_ctrl' ? 'neg ctrl' : 'pos ctrl'}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: 'Unclassified %', fn: s => fmtPct(s.taxprofiler?.kraken2?.pct_unclassified) },
                      { label: 'Species', fn: s => fmt(s.taxprofiler?.kraken2?.num_species) },
                      { label: 'Genera', fn: s => fmt(s.taxprofiler?.kraken2?.num_genera) },
                      { label: 'Q30 rate', fn: s => fmtPct(s.taxprofiler?.fastp?.q30_rate ? s.taxprofiler.fastp.q30_rate * 100 : null) },
                      { label: 'Host reads', fn: s => fmtPct(s.taxprofiler?.bowtie2?.overall_alignment_rate) },
                    ].map(row => (
                      <tr key={row.label} className="border-t border-gray-50">
                        <td className="py-2 pr-4 text-xs text-gray-500">{row.label}</td>
                        {[...testSamples, ...controls].map(s => (
                          <td key={s._id} className="py-2 px-3 text-xs text-gray-700 text-right">
                            {row.fn(s)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}