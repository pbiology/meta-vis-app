import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getMetavalResult, getReadsDownloadUrl } from '../api/metaval'

function ReadCountBadge({ fasta }) {
  // Count sequences by counting '>' at start of lines
  const count = (fasta.match(/^>/gm) ?? []).length
  return (
    <span className="text-xs text-gray-500 tabular-nums">
      {count.toLocaleString()} {count === 1 ? 'read' : 'reads'}
    </span>
  )
}

function ReadsSection({ metavalId, result }) {
  const reads = result?.extracted_reads ?? {}

  const [preview, setPreview] = useState({ 1: null, 2: null })
  const [loading, setLoading] = useState({ 1: false, 2: false })
  const [error,   setError]   = useState({ 1: null,  2: null  })

  async function loadPreview(readNum) {
    setLoading(p => ({ ...p, [readNum]: true }))
    setError(p =>   ({ ...p, [readNum]: null }))
    try {
      const url  = getReadsDownloadUrl(metavalId, readNum)
      const res  = await fetch(url, { credentials: 'include' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const text = await res.text()
      setPreview(p => ({ ...p, [readNum]: text }))
    } catch (e) {
      setError(p => ({ ...p, [readNum]: 'Failed to load reads.' }))
    } finally {
      setLoading(p => ({ ...p, [readNum]: false }))
    }
  }

  const rows = [
    { num: 1, label: 'Read 1', available: reads.has_read_1 },
    { num: 2, label: 'Read 2', available: reads.has_read_2 },
  ]

  const anyAvailable = rows.some(r => r.available)

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
          Extracted reads
        </p>
        {!anyAvailable && (
          <span className="text-xs text-gray-300">Not available</span>
        )}
      </div>

      {anyAvailable ? (
        <div className="divide-y divide-gray-50">
          {rows.map(({ num, label, available }) => (
            <div key={num} className="px-5 py-4">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs font-medium text-gray-600">{label}</span>

                {available ? (
                  <>
                    {preview[num] && <ReadCountBadge fasta={preview[num]} />}
                    <div className="flex items-center gap-2 ml-auto">
                      <button
                        onClick={() => loadPreview(num)}
                        disabled={loading[num]}
                        className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-40 transition-colors"
                      >
                        {loading[num] ? 'Loading…' : preview[num] ? 'Reload' : 'Preview'}
                      </button>
                      <a
                        href={getReadsDownloadUrl(metavalId, num)}
                        download
                        className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
                      >
                        <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
                          <path d="M8 2v8M5 7l3 3 3-3M3 12h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                        Download .fa
                      </a>
                    </div>
                  </>
                ) : (
                  <span className="text-xs text-gray-300 ml-auto">Not available</span>
                )}
              </div>

              {error[num] && (
                <p className="text-xs text-red-400">{error[num]}</p>
              )}

              {preview[num] && !error[num] && (
                <pre className="text-xs font-mono text-gray-500 bg-gray-50 rounded-lg p-3 overflow-x-auto whitespace-pre leading-relaxed max-h-64 overflow-y-auto">
                  {/* Show first 10 sequences only */}
                  {preview[num]
                    .split('\n')
                    .reduce((acc, line) => {
                      if (line.startsWith('>')) acc.headers++
                      if (acc.headers <= 10) acc.lines.push(line)
                      return acc
                    }, { lines: [], headers: 0 })
                    .lines.join('\n')}
                  {(preview[num].match(/^>/gm) ?? []).length > 10 && (
                    '\n…'
                  )}
                </pre>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="px-5 py-8 text-xs text-gray-300 text-center">
          No extracted reads were ingested for this taxon.
        </p>
      )}
    </section>
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

      {/* Topbar */}
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5">
        <ReadsSection metavalId={metavalId} result={result} />
      </div>

    </div>
  )
}