import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getMetavalResult, getIgvUrl } from '../api/metaval'

export default function MetavalDetails() {
  const { sampleId, metavalId } = useParams()
  const navigate = useNavigate()

  const [result,       setResult]       = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState(null)
  const [selectedOrg,  setSelectedOrg]  = useState(null)
  const [igvUrl,       setIgvUrl]       = useState(null)
  const [igvLoading,   setIgvLoading]   = useState(false)
  const [igvError,     setIgvError]     = useState(null)

  useEffect(() => {
    getMetavalResult(metavalId)
      .then(data => {
        setResult(data)
        if (data.organisms?.length) {
          selectOrganism(metavalId, data.organisms[0])
        }
      })
      .catch(() => setError('Failed to load metaval result.'))
      .finally(() => setLoading(false))
  }, [metavalId])

  async function selectOrganism(mvId, org) {
    setSelectedOrg(org.organism_name)
    setIgvUrl(null)
    setIgvError(null)
    if (org.igv_too_large) {
      setIgvError('IGV file exceeds 10 MB and cannot be displayed.')
      return
    }
    setIgvLoading(true)
    try {
      const url = await getIgvUrl(mvId, org.organism_name)
      setIgvUrl(url)
    } catch {
      setIgvError('Failed to load IGV report.')
    } finally {
      setIgvLoading(false)
    }
  }

  if (loading) return <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
  if (error)   return <div className="flex items-center justify-center h-full text-sm text-red-500">{error}</div>

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
        <h1 className="text-sm font-medium text-gray-900 flex-1 font-mono">
          {result?.taxon_name?.replace(/-/g, ' ')}
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 px-6 py-5 flex flex-col gap-6">

        {/* Organisms table */}
        <section className="bg-white border border-gray-100 rounded-xl">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Mapping organisms</p>
          </div>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr>
                {['Organism', 'IGV size', ''].map(h => (
                  <th key={h} className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result?.organisms?.map(org => (
                <tr
                  key={org.organism_name}
                  onClick={() => selectOrganism(metavalId, org)}
                  className={`cursor-pointer border-b border-gray-50 transition-colors ${
                    selectedOrg === org.organism_name ? 'bg-gray-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <td className="px-4 py-2.5 text-xs font-mono text-gray-700">
                    {org.organism_name.replace(/-/g, ' ')}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-400">
                    {org.igv_too_large
                      ? <span className="text-red-400">{'>'} 10 MB</span>
                      : `${(org.igv_file_size_bytes / 1024).toFixed(0)} KB`
                    }
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {selectedOrg === org.organism_name && (
                      <span className="text-xs text-blue-500">viewing</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* IGV viewer */}
        <section className="bg-white border border-gray-100 rounded-xl">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              IGV
              {selectedOrg && (
                <span className="ml-2 normal-case font-normal text-gray-300 font-mono">
                  — {selectedOrg.replace(/-/g, ' ')}
                </span>
              )}
            </p>
          </div>
          <div className="p-4">
            {igvError && <p className="text-xs text-red-400">{igvError}</p>}
            {igvLoading && (
              <div className="flex items-center justify-center h-40 text-sm text-gray-400">Loading IGV…</div>
            )}
            {igvUrl && !igvLoading && (
              <iframe
                src={igvUrl}
                title="IGV report"
                className="w-full rounded-lg border border-gray-100"
                style={{ height: '75vh' }}
                sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
              />
            )}
            {!igvUrl && !igvLoading && !igvError && (
              <div className="flex items-center justify-center h-40 text-sm text-gray-400">
                Select an organism above to view the IGV report.
              </div>
            )}
          </div>
        </section>

      </div>
    </div>
  )
}