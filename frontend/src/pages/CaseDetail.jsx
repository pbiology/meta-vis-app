import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getCase, getCaseSamples, reviewCase, getCaseKronaUrl } from '../api/cases'
import Badge from '../components/Badge'
import MetricCard from '../components/MetricCard'

function fmt(n) {
  if (n === undefined || n === null) return '—'
  return typeof n === 'number' ? n.toLocaleString() : n
}

function fmtPct(n) {
  if (n === undefined || n === null) return '—'
  return `${n.toFixed(1)}%`
}

const FILTERS = ['All', 'Test', 'Controls']

export default function CaseDetail() {
  const { caseId } = useParams()
  const navigate = useNavigate()

  const [caseData,  setCaseData]  = useState(null)
  const [samples,   setSamples]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(null)
  const [filter,    setFilter]    = useState('All')
  const [reviewing, setReviewing] = useState(false)

  // Krona
  const [kronaUrl,   setKronaUrl]   = useState(null)
  const [kronaError, setKronaError] = useState(false)
  const [kronaOpen,  setKronaOpen]  = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const [fetchedCase, samplesData] = await Promise.all([
          getCase(caseId),
          getCaseSamples(caseId),
        ])
        setCaseData(fetchedCase)
        setSamples(samplesData)
        if (fetchedCase.has_krona) {
          try {
            const url = await getCaseKronaUrl(caseId)
            setKronaUrl(url)
          } catch {
            setKronaError(true)
          }
        }
      } catch {
        setError('Failed to load case.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [caseId])

  async function handleReview() {
    setReviewing(true)
    try {
      await reviewCase(caseId)
      setCaseData(prev => ({ ...prev, review: { ...prev.review, reviewed: true } }))
    } catch {
      alert('Failed to mark as reviewed.')
    } finally {
      setReviewing(false)
    }
  }

  const filtered = useMemo(() => {
    if (filter === 'Test')     return samples.filter(s => s.sample_type === 'test')
    if (filter === 'Controls') return samples.filter(s =>
      s.sample_type === 'negative_ctrl' || s.sample_type === 'positive_ctrl'
    )
    return samples
  }, [samples, filter])

  const testSamples = samples.filter(s => s.sample_type === 'test')
  const controls    = samples.filter(s =>
    s.sample_type === 'negative_ctrl' || s.sample_type === 'positive_ctrl'
  )

  const reviewed = caseData?.review?.reviewed

    if (kronaOpen && kronaUrl) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
          <button
            onClick={() => navigate('/cases')}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
          >
            <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
              <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Cases
          </button>
          <span className="text-gray-200">/</span>
          <span className="text-xs text-gray-400 font-mono">{caseId}</span>
          <span className="text-gray-200">/</span>
          <h1 className="text-sm font-medium text-gray-900 flex-1">Krona</h1>
          <button
            onClick={() => setKronaOpen(false)}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            ← Back to case
          </button>
        </div>
        <iframe
          src={kronaUrl}
          title="Krona taxonomic chart"
          className="flex-1 w-full"
          sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
        />
      </div>
    )
  }

  if (loading) return <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
  if (error)   return <div className="flex items-center justify-center h-full text-sm text-red-500">{error}</div>

  return (
    <div className="flex flex-col h-full">

      {/* Topbar */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate('/cases')}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Cases
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 font-mono flex-1">{caseId}</h1>
        <Badge type={reviewed ? 'reviewed' : 'pending'} />
        {!reviewed && (
          <button
            onClick={handleReview}
            disabled={reviewing}
            className="btn-primary disabled:opacity-50"
          >
            {reviewing ? 'Saving…' : 'Mark case as reviewed'}
          </button>
        )}
        {reviewed && (
          <span className="text-xs text-gray-400">Reviewed by {caseData.review.reviewed_by}</span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 px-6 py-5 flex flex-col gap-6">

        {/* Samples table */}
        <section className="bg-white border border-gray-100 rounded-xl">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">Samples</p>
            <div className="flex gap-1.5">
              {FILTERS.map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                    filter === f
                      ? 'bg-gray-900 text-white font-medium'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr>
                {['Sample ID', 'Material', 'Order date', 'Type', 'Unclassified', 'Q30', 'Top taxa'].map(h => (
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
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{s.sample?.sample_id ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{s.material ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{s.order_date ?? '—'}</td>
                  <td className="px-4 py-3"><Badge type={s.sample_type} /></td>
                  <td className="px-4 py-3 text-xs text-gray-700">{fmtPct(s.taxprofiler?.kraken2?.pct_unclassified)}</td>
                  <td className="px-4 py-3 text-xs text-gray-700">
                    {fmtPct(s.taxprofiler?.fastp?.q30_rate ? s.taxprofiler.fastp.q30_rate * 100 : null)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      {(s.top_taxa || []).map((t, i) => (
                        <span key={i} className="text-xs text-gray-600 italic truncate max-w-48">
                          <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 flex-shrink-0 ${
                            t.superkingdom === 'Bacteria'  ? 'bg-blue-400'   :
                            t.superkingdom === 'Viruses'   ? 'bg-red-400'    :
                            t.superkingdom === 'Eukaryota' ? 'bg-amber-400'  :
                            t.superkingdom === 'Archaea'   ? 'bg-purple-400' : 'bg-gray-300'
                          }`} />
                          {t.name}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-400">No samples match this filter.</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        {/* Krona */}
        {caseData?.has_krona && (
          <section className="bg-white border border-gray-100 rounded-xl">
            <div className="flex items-center gap-2 px-4 py-3">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">Krona</p>
              {kronaError && <span className="text-xs text-red-400">Could not load</span>}
              {!kronaUrl && !kronaError && <span className="text-xs text-gray-300">Loading…</span>}
              {kronaUrl && (
                <div
                  onClick={() => setKronaOpen(true)}
                  className="flex items-center gap-1.5 cursor-pointer text-xs text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
                    <path d="M3 3h4M3 3v4M13 3h-4M13 3v4M3 13h4M3 13v-4M13 13h-4M13 13v-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                  Open full screen
                </div>
              )}
            </div>
          </section>
        )}

        {/* Controls comparison */}
        {controls.length > 0 && (
          <section className="bg-white border border-gray-100 rounded-xl p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Controls comparison</p>
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
                  { label: 'Species',        fn: s => fmt(s.taxprofiler?.kraken2?.num_species) },
                  { label: 'Genera',         fn: s => fmt(s.taxprofiler?.kraken2?.num_genera) },
                  { label: 'Q30 rate',       fn: s => fmtPct(s.taxprofiler?.fastp?.q30_rate ? s.taxprofiler.fastp.q30_rate * 100 : null) },
                  { label: 'Host reads',     fn: s => fmtPct(s.taxprofiler?.bowtie2?.overall_alignment_rate) },
                ].map(row => (
                  <tr key={row.label} className="border-t border-gray-50">
                    <td className="py-2 pr-4 text-xs text-gray-500">{row.label}</td>
                    {[...testSamples, ...controls].map(s => (
                      <td key={s._id} className="py-2 px-3 text-xs text-gray-700 text-right">{row.fn(s)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

      </div>
    </div>
  )
}