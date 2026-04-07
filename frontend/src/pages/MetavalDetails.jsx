import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getMetavalResult, submitBlast } from '../api/metaval'

function BlastModal({ onClose }) {
  const [status, setStatus] = useState('blasting')
  const [error,  setError]  = useState(null)
  const { metavalId } = useParams()

  useEffect(() => {
    submitBlast(metavalId)
      .then(data => {
        window.open(data.results_url, '_blank')
        onClose()
      })
      .catch(err => {
        const msg = err?.response?.data?.detail ?? 'BLAST submission failed. Please try again.'
        setError(msg)
        setStatus('error')
      })
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-xl px-8 py-7 max-w-sm w-full mx-4 flex flex-col gap-4">
        {status === 'blasting' && (
          <>
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 animate-spin text-blue-500 flex-shrink-0" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="28" strokeDashoffset="10"/>
              </svg>
              <p className="text-sm font-medium text-gray-800">Submitting to NCBI BLAST…</p>
            </div>
            <p className="text-xs text-gray-400">This can take up to 30 seconds.</p>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-red-400 flex-shrink-0" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M8 5v3M8 10.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <p className="text-sm font-medium text-gray-800">Submission failed</p>
            </div>
            <p className="text-xs text-red-400">{error}</p>
            <button
              onClick={onClose}
              className="self-end text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Dismiss
            </button>
          </>
        )}
      </div>
    </div>
  )
}

const TYPE_LABEL = {
  scaffolds: 'Scaffolds',
  contigs:   'Contigs',
  raw_reads: 'Raw reads',
}

function VerificationDataSection({ result }) {
  const [showBlast, setShowBlast] = useState(false)

  const vd = result?.verification_data ?? {}

  return (
    <>
      {showBlast && <BlastModal onClose={() => setShowBlast(false)} />}

      <section className="bg-white border border-gray-100 rounded-xl">
        <div className="px-5 py-3.5 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Taxon verification data
          </p>
        </div>

        {vd.type ? (
          <table className="w-full text-left">
            <thead>
              <tr>
                {['Type', 'Sequences', 'Avg length', 'Data availability', ''].map(h => (
                  <th key={h} className="px-5 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="px-5 py-2.5 text-xs text-gray-600">
                  {TYPE_LABEL[vd.type] ?? vd.type}
                </td>
                <td className="px-5 py-2.5 text-xs text-gray-500 tabular-nums">
{                 vd.count != null
                    ? vd.type === 'raw_reads'
                      ? `${vd.count.toLocaleString()} × ${vd.file_count ?? 1} (${(vd.file_count ?? 1) > 1 ? 'paired-end' : 'single-end'})`
                      : vd.count.toLocaleString()
                    : '—'
                  }
                </td>
                <td className="px-5 py-2.5 text-xs text-gray-500 tabular-nums">
                  {vd.avg_length != null ? `${vd.avg_length} bp` : '—'}
                </td>
                <td className="px-5 py-2.5 text-xs text-gray-400">
                  {vd.available ? 'Available' : <span className="text-gray-300">Not available</span>}
                </td>
                <td className="px-5 py-2.5 text-right">
                  {vd.available && (
                    <button
                      onClick={() => setShowBlast(true)}
                      className="text-xs px-3 py-1 rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
                    >
                      BLAST
                    </button>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="px-5 py-8 text-xs text-gray-300 text-center">
            No verification data was ingested for this taxon.
          </p>
        )}
      </section>
    </>
  )
}

export default function MetavalDetails() {
  const { sampleId, metavalId } = useParams()
  const navigate = useNavigate()

  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    getMetavalResult(metavalId)
      .then(setResult)
      .catch(() => setError('Failed to load metaval result.'))
      .finally(() => setLoading(false))
  }, [metavalId])

  if (loading) return (
    <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
  )
  if (error) return (
    <div className="flex items-center justify-center h-full text-sm text-red-500">{error}</div>
  )

  const taxonLabel = result?.taxon_name?.replace(/-/g, ' ') ?? '—'

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate(`/samples/${sampleId}`)}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>
        <span className="text-gray-200">/</span>
        <span className="text-xs text-gray-400 font-mono">{result?.sample_name}</span>
        <span className="text-gray-200">/</span>
        <span className="text-xs text-gray-400">{result?.classifier}</span>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 italic">{taxonLabel}</h1>
        {result?.taxon_id && (
          <a
            href={`https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${result.taxon_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 text-xs text-gray-400 hover:text-blue-500 font-mono transition-colors"
            title="Open in NCBI Taxonomy Browser"
          >
            taxid:{result.taxon_id}
          </a>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5">
        <VerificationDataSection result={result} />
      </div>
    </div>
  )
}