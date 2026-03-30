import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getCase, getCaseSamples, reviewCase, unreviewCase, getCaseKronaUrl } from '../api/cases'
import Badge from '../components/Badge'
import { useAuth } from '../context/AuthContext'

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
  const navigate   = useNavigate()
  const { role }   = useAuth()

  const [caseData,        setCaseData]        = useState(null)
  const [samples,         setSamples]         = useState([])
  const [loading,         setLoading]         = useState(true)
  const [error,           setError]           = useState(null)
  const [filter,          setFilter]          = useState('All')
  const [reviewing,       setReviewing]       = useState(false)
  const [unreviewConfirm, setUnreviewConfirm] = useState(false)
  const [kronaUrl,        setKronaUrl]        = useState(null)
  const [kronaError,      setKronaError]      = useState(false)
  const [provenanceOpen,  setProvenanceOpen]  = useState(false)

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
      const result = await reviewCase(caseId)
      setCaseData(prev => ({
        ...prev,
        review: { ...prev.review, reviewed: true, reviewed_by: result.reviewed_by },
      }))
    } catch {
      alert('Failed to mark as reviewed.')
    } finally {
      setReviewing(false)
    }
  }

  async function handleUnreview() {
    setUnreviewConfirm(false)
    setReviewing(true)
    try {
      await unreviewCase(caseId)
      setCaseData(prev => ({
        ...prev,
        review: { reviewed: false, reviewed_by: null, reviewed_at: null, notes: null },
      }))
    } catch {
      alert('Failed to remove review.')
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
        {!reviewed && role !== 'reader' && (
          <button
            onClick={handleReview}
            disabled={reviewing}
            className="btn-primary disabled:opacity-50"
          >
            {reviewing ? 'Saving…' : 'Mark case as reviewed'}
          </button>
        )}
        {reviewed && (
          <>
            <button
              onClick={() => setUnreviewConfirm(true)}
              className="text-xs text-green-600 hover:text-green-800 transition-colors"
            >
              ● Reviewed by {caseData.review.reviewed_by}
            </button>
            {unreviewConfirm && (
              <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
                <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
                  <p className="text-sm font-medium text-gray-900">Remove review?</p>
                  <p className="text-xs text-gray-500">
                    This will remove the review by <span className="font-medium">{caseData.review.reviewed_by}</span> and reset the case to pending. This cannot be undone.
                  </p>
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => setUnreviewConfirm(false)} className="btn-secondary">Cancel</button>
                    <button onClick={handleUnreview} className="btn-primary">Remove review</button>
                  </div>
                </div>
              </div>
            )}
          </>
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
                    filter === f ? 'bg-gray-900 text-white font-medium' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
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
                        <span key={i} className="flex items-center gap-1 text-xs">
                          <span className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                            t.superkingdom === 'Bacteria'  ? 'bg-blue-400'   :
                            t.superkingdom === 'Viruses'   ? 'bg-red-400'    :
                            t.superkingdom === 'Eukaryota' ? 'bg-amber-400'  :
                            t.superkingdom === 'Archaea'   ? 'bg-purple-400' : 'bg-gray-300'
                          }`} />
                          <span className="text-gray-600 italic truncate max-w-36">{t.name}</span>
                          {t.pct != null && (
                            <span className="text-gray-400 flex-shrink-0">{t.pct}%</span>
                          )}
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
          <section className="bg-white border border-gray-100 rounded-xl p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Krona</p>
            {kronaError && <p className="text-xs text-red-400">Krona file could not be loaded.</p>}
            {!kronaUrl && !kronaError && (
              <div className="flex items-center justify-center h-40 text-sm text-gray-400">Loading Krona…</div>
            )}
            {kronaUrl && (
              <iframe
                src={kronaUrl}
                title="Krona taxonomic chart"
                className="w-full rounded-lg border border-gray-100"
                style={{ height: '85vh' }}
                sandbox="allow-scripts allow-popups allow-forms"
              />
            )}
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

        {/* Provenance */}
        {caseData && caseData.pipeline_info ? (
          <section className="bg-white border border-gray-100 rounded-xl">
            <button
              onClick={() => setProvenanceOpen(o => !o)}
              className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
            >
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">Provenance</p>
              <svg
                className={`w-3 h-3 text-gray-300 transition-transform ${provenanceOpen ? 'rotate-180' : ''}`}
                viewBox="0 0 16 16" fill="none"
              >
                <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            {provenanceOpen && (() => {
              const pipelineConfig = caseData.pipeline_info.pipeline_configuration || {}
              const toolMap = {}
              Object.values(caseData.pipeline_info.software_used || {}).forEach(processTools => {
                Object.entries(processTools).forEach(([name, ver]) => {
                  toolMap[String(name)] = String(ver)
                })
              })
              const toolRows = Object.entries(toolMap).sort()
              return (
                <div className="border-t border-gray-100 px-4 py-3 flex flex-col gap-3">
                  <div className="flex gap-6">
                    {pipelineConfig.pipeline && (
                      <span className="text-xs text-gray-500">
                        <span className="text-gray-400">nf-core/taxprofiler</span>
                        <span className="font-mono ml-2 text-gray-700">{String(pipelineConfig.pipeline)}</span>
                      </span>
                    )}
                    {pipelineConfig.nextflow && (
                      <span className="text-xs text-gray-500">
                        <span className="text-gray-400">Nextflow</span>
                        <span className="font-mono ml-2 text-gray-700">{String(pipelineConfig.nextflow)}</span>
                      </span>
                    )}
                  </div>
                  <table className="w-full">
                    <thead>
                      <tr>
                        <th className="text-left text-xs font-medium text-gray-400 pb-1.5 w-1/2">Tool</th>
                        <th className="text-left text-xs font-medium text-gray-400 pb-1.5">Version</th>
                      </tr>
                    </thead>
                    <tbody>
                      {toolRows.map(([name, ver]) => (
                        <tr key={name} className="border-t border-gray-50">
                          <td className="py-1 text-xs text-gray-600">{name}</td>
                          <td className="py-1 font-mono text-xs text-gray-400">{ver}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            })()}
          </section>
        ) : null}

      </div>
    </div>
  )
}