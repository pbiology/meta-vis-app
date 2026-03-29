export default function MetricCard({ label, value, sub, warn = false }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-xl font-medium ${warn ? 'text-amber-600' : 'text-gray-900'}`}>
        {value ?? '—'}
      </div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}