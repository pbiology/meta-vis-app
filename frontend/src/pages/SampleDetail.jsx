import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getSample, getProfile, reviewSample, getRunControls } from '../api/samples'
import Badge from '../components/Badge'
import MetricCard from '../components/MetricCard'

function fmt(n, decimals = 0) {
  if (n === undefined || n === null) return '—'
  return typeof n === 'number' ? n.toLocaleString(undefined, { maximumFractionDigits: decimals }) : n
}

function fmtPct(n) {
  if (n === undefined || n === null) return '—'
  return `${n.toFixed(1)}%`
}

function AbundanceBar({ value, max }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 bg-gray-100 rounded-full h-1.5 flex-shrink-0">
        <div className="bg-blue-400 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500">{fmt(value)}</span>
    </div>
  )
}

export default function SampleDetail() {
  const { sampleId } = useParams()
  const navigate = useNavigate()
  const [sample, setSample] = useState(null)
  const [profile, setProfile] = useState(null)
  const [controls, setControls] = useState([])
  const [loading, setLoading] = useState(true)
  const [reviewing, setReviewing] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const [s, p] = await Promise.all([getSample(sampleId), getProfile(sampleId)])
        setSample(s)
        setProfile(p)
        // Fetch controls for this run
        if (s.run_id_str || s.run_id) {
          // run_id_str might not be set here — we need to find run_id string
          // The sample's run_id is an ObjectId string; fetch controls via run_id_str if available
          // We'll store it from the full sample document indirectly
        }
      } catch {
        setError('Failed to load sample.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [sampleId])

  // Fetch controls once we have run info
  useEffect(() => {
    if (!sample) return
    // The sample detail endpoint doesn't include run_id_str, so we skip controls
    // if we don't have it. This is improved once runs endpoint is cross-referenced.
    // For now, controls can be loaded if the sample list page passed state.
  }, [sample])

  async function handleReview() {
    setReviewing(true)
    try {
      await reviewSample(sampleId)
      setSample(prev => ({
        ...prev,
        review: { ...prev.review, reviewed: true },
      }))
    } catch {
      alert('Failed to mark as reviewed.')
    } finally {
      setReviewing(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
  )
  if (error) return (
    <div className="flex items-center justify-center h-full text-sm text-red-500">{error}</div>
  )

  const qc = sample?.taxprofiler
  const k2 = qc?.kraken2
  const fp = qc?.fastp
  const fq = qc?.fastqc
  const bt = qc?.bowtie2
  const reviewed = sample?.review?.reviewed

  // Top organisms from first profile
  const topOrganisms = profile?.profiles?.[0]?.profile
    ?.slice()
    .sort((a, b) => b.abundance - a.abundance)
    .slice(0, 10) ?? []
  const maxAbundance = topOrganisms[0]?.abundance ?? 1

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate('/samples')}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          All samples
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 flex-1 font-mono">
          {sample?.sample?.sample_id ?? sampleId}
        </h1>
        <Badge type={sample?.sample_type} />
        <Badge type={reviewed ? 'reviewed' : 'pending'} />
        {!reviewed && (
          <button
            onClick={handleReview}
            disabled={reviewing}
            className="btn-primary disabled:opacity-50"
          >
            {reviewing ? 'Saving…' : 'Mark as reviewed'}
          </button>
        )}
        {reviewed && (
          <span className="text-xs text-gray-400">
            Reviewed by {sample.review.reviewed_by}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">

        {/* QC metrics */}
        <section>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">QC metrics</p>
          <div className="grid grid-cols-4 gap-2.5">
            <MetricCard label="Total reads" value={fp ? fmt(fp.total_reads_before_filtering) : '—'} sub="before filtering" />
            <MetricCard label="Passed filter" value={fp ? fmt(fp.passed_filter_reads) : '—'} sub={fp ? `${fmtPct((fp.passed_filter_reads / fp.total_reads_before_filtering) * 100)} of raw` : ''} />
            <MetricCard label="Host removed" value={bt ? fmtPct(bt.overall_alignment_rate) : '—'} sub="bowtie2 alignment" />
            <MetricCard label="Unclassified" value={fmtPct(k2?.pct_unclassified)} sub={k2 ? `${fmt(k2.unclassified_reads)} reads` : ''} warn={(k2?.pct_unclassified ?? 0) > 20} />
            <MetricCard label="Q20 rate" value={fmtPct(fp?.q20_rate ? fp.q20_rate * 100 : null)} sub="fastp" />
            <MetricCard label="Q30 rate" value={fmtPct(fp?.q30_rate ? fp.q30_rate * 100 : null)} sub="fastp" />
            <MetricCard label="Species" value={fmt(k2?.num_species)} sub="kraken2" />
            <MetricCard label="Genera" value={fmt(k2?.num_genera)} sub="kraken2" />
          </div>
        </section>

        {/* Taxonomy + controls side by side */}
        <div className="grid grid-cols-2 gap-4">

          {/* Top organisms */}
          <section className="bg-white border border-gray-100 rounded-xl p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
              Top organisms
              {profile?.profiles?.[0] && (
                <span className="ml-2 normal-case font-normal text-gray-300">
                  {profile.profiles[0].classifier} · {profile.profiles[0].classifier_db}
                </span>
              )}
            </p>
            {topOrganisms.length === 0 ? (
              <p className="text-xs text-gray-400">No profile data available.</p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="text-left text-xs font-medium text-gray-400 pb-2">Taxon</th>
                    <th className="text-right text-xs font-medium text-gray-400 pb-2 pr-2">Reads</th>
                    <th className="text-left text-xs font-medium text-gray-400 pb-2 pl-2">Abundance</th>
                  </tr>
                </thead>
                <tbody>
                  {topOrganisms.map((t, i) => (
                    <tr key={i} className="border-t border-gray-50">
                      <td className="py-2 text-xs text-gray-700 pr-3 italic">{t.name}</td>
                      <td className="py-2 text-xs text-gray-500 text-right pr-2">{fmt(t.abundance)}</td>
                      <td className="py-2 pl-2">
                        <AbundanceBar value={t.abundance} max={maxAbundance} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {/* Controls comparison */}
          <section className="bg-white border border-gray-100 rounded-xl p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Controls comparison</p>
            {controls.length === 0 ? (
              <div className="text-xs text-gray-400 space-y-1">
                <p>Controls are fetched from the same run.</p>
                <p className="text-gray-300">Navigate to this sample from the sample list to load run context, or view the run directly.</p>
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="text-left text-xs font-medium text-gray-400 pb-2">Metric</th>
                    {controls.map(c => (
                      <th key={c._id} className="text-right text-xs font-medium text-gray-400 pb-2">
                        {c.sample?.sample_id}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: 'Unclassified %', fn: s => fmtPct(s.taxprofiler?.kraken2?.pct_unclassified) },
                    { label: 'Species', fn: s => fmt(s.taxprofiler?.kraken2?.num_species) },
                    { label: 'Q30 rate', fn: s => fmtPct(s.taxprofiler?.fastp?.q30_rate ? s.taxprofiler.fastp.q30_rate * 100 : null) },
                  ].map(row => (
                    <tr key={row.label} className="border-t border-gray-50">
                      <td className="py-2 text-xs text-gray-500">{row.label}</td>
                      {controls.map(c => (
                        <td key={c._id} className="py-2 text-xs text-gray-700 text-right">
                          {row.fn(c)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

        </div>
      </div>
    </div>
  )
}