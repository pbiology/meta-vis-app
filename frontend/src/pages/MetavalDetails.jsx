import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getMetavalResult, submitBlast, getIgvUrl } from '../api/metaval'

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

function BlastResultsSection({ blast }) {
  const COLUMNS = [
    { key: 'qseqid',          label: 'Query'         },
    { key: 'ssciname',        label: 'Match'         },
    { key: 'staxid',          label: 'Tax ID'        },
    { key: 'median_pident',   label: '% identity'    },
    { key: 'median_length',   label: 'Length'        },
    { key: 'median_bitscore', label: 'Bitscore'      },
    { key: 'count',           label: 'Hits'          },
  ]

  function sortedRows(rows) {
    return [...rows].sort((a, b) =>
      parseFloat(b.median_bitscore ?? 0) - parseFloat(a.median_bitscore ?? 0)
    )
  }

function BlastTable({ rows, program }) {
    const [open, setOpen] = useState(true)
    return (
      <div className="border-t border-gray-50 first:border-t-0">
        <button
          onClick={() => setOpen(o => !o)}
          className="w-full flex items-center justify-between px-5 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="text-xs font-medium text-gray-500">{program}</span>
          <div className="flex items-center gap-2">
            {rows.length > 0 && (
              <span className="text-xs text-gray-400">{rows.length} {rows.length === 1 ? 'hit' : 'hits'}</span>
            )}
            <svg
              className={`w-3 h-3 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
              viewBox="0 0 16 16" fill="none"
            >
              <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        </button>
        {open && (
          rows.length === 0 ? (
            <p className="px-5 py-4 text-xs text-gray-300">No hits</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr>
                    {COLUMNS.map(c => (
                      <th key={c.key} className="px-5 py-2 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap">
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedRows(rows).map((row, i) => (
                    <tr key={i} className="border-t border-gray-50 hover:bg-gray-50">
                      <td className="px-5 py-2 text-xs font-mono text-gray-600 max-w-48 truncate" title={row.qseqid}>
                        {row.qseqid}
                      </td>
                      <td className="px-5 py-2 text-xs italic text-gray-700">{row.ssciname}</td>
                      <td className="px-5 py-2 text-xs font-mono text-gray-400">{row.staxid}</td>
                      <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">{row.median_pident}</td>
                      <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">{row.median_length}</td>
                      <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">{row.median_bitscore}</td>
                      <td className="px-5 py-2 text-xs text-gray-500 tabular-nums">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    )
  }

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="px-5 py-3.5 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">BLAST results</p>
      </div>
      <BlastTable rows={blast?.blastn ?? []} program="BLASTn" />
      <BlastTable rows={blast?.blastx ?? []} program="BLASTx" />
    </section>
  )
}

function CandidateOrganismsSection({ metavalId, organisms }) {
  const [selected,   setSelected]   = useState(null)
  const [igvUrl,     setIgvUrl]     = useState(null)
  const [igvLoading, setIgvLoading] = useState(false)
  const [igvError,   setIgvError]   = useState(null)

  async function handleSelect(org) {
    if (selected === org.organism_name) return
    setSelected(org.organism_name)
    setIgvUrl(null)
    setIgvError(null)
    if (org.igv_too_large) {
      setIgvError('IGV file exceeds 10 MB and cannot be displayed.')
      return
    }
    setIgvLoading(true)
    try {
      const url = await getIgvUrl(metavalId, org.organism_name)
      setIgvUrl(url)
    } catch {
      setIgvError('Failed to load IGV report.')
    } finally {
      setIgvLoading(false)
    }
  }

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="px-5 py-3.5 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          Candidate organisms
        </p>
      </div>

      {!organisms || organisms.length === 0 ? (
        <p className="px-5 py-8 text-xs text-gray-300 text-center">
          No predicted candidate found
        </p>
      ) : (
        <>
          <table className="w-full text-left">
            <thead>
              <tr>
                {['Organism', 'IGV size', ''].map(h => (
                  <th key={h} className="px-5 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {organisms.map(org => (
                <tr
                  key={org.organism_name}
                  onClick={() => handleSelect(org)}
                  className={`cursor-pointer border-t border-gray-50 transition-colors ${
                    selected === org.organism_name ? 'bg-blue-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <td className="px-5 py-2.5 text-xs italic text-gray-700">
                    {org.organism_name.replace(/-/g, ' ')}
                  </td>
                  <td className="px-5 py-2.5 text-xs text-gray-400 tabular-nums">
                    {org.igv_too_large
                      ? <span className="text-red-400">&gt; 10 MB</span>
                      : `${(org.igv_file_size_bytes / 1024).toFixed(0)} KB`
                    }
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    {selected === org.organism_name && (
                      <span className="text-xs text-blue-500">viewing</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {selected && (
            <div className="border-t border-gray-100 p-5">
              {igvError && (
                <p className="text-xs text-red-400">{igvError}</p>
              )}
              {igvLoading && (
                <div className="flex items-center justify-center h-40 text-sm text-gray-400">
                  Loading IGV…
                </div>
              )}
              {igvUrl && !igvLoading && (
                <iframe
                  src={igvUrl}
                  title="IGV report"
                  className="w-full rounded-lg border border-gray-100"
                  style={{ height: '75vh' }}
                  sandbox="allow-scripts allow-popups allow-forms"
                />
              )}
            </div>
          )}
        </>
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
        <BlastResultsSection blast={result?.blast} />
        <CandidateOrganismsSection metavalId={metavalId} organisms={result?.organisms} />
      </div>
    </div>
  )
}