import { Link } from "react-router-dom";

export interface NtcPipelineOption {
  value: string;
  label: string;
}

interface NtcFiltersBarProps {
  material: string;
  pipeline: string;
  windowDays: number;
  minReads: number;
  minAbundance: number;
  minCasePct: number;
  availablePipelines: NtcPipelineOption[];
  onMaterialChange: (material: string) => void;
  onPipelineChange: (pipeline: string) => void;
  onWindowDaysChange: (days: number) => void;
  onMinReadsChange: (n: number) => void;
  onMinAbundanceChange: (n: number) => void;
  onMinCasePctChange: (pct: number) => void;
}

const MATERIALS = ["DNA", "RNA"];
const WINDOWS = [30, 90, 180];
const MIN_READS_OPTIONS = [1, 3, 5, 10, 20];
const MIN_CASE_PCT_OPTIONS = [5, 10, 20, 25, 50];
const MIN_ABUNDANCE_OPTIONS = [
  { value: 0.001, label: "0.1%" },
  { value: 0.005, label: "0.5%" },
  { value: 0.01, label: "1%" },
  { value: 0.05, label: "5%" },
];

const PILL_BASE = "px-3 py-1 rounded-full text-xs transition-colors";
const PILL_ACTIVE = "bg-gray-900 text-white font-medium";
const PILL_INACTIVE = "bg-gray-100 text-gray-500 hover:bg-gray-200";

function pillClass(active: boolean) {
  return `${PILL_BASE} ${active ? PILL_ACTIVE : PILL_INACTIVE}`;
}

export default function NtcFiltersBar({
  material,
  pipeline,
  windowDays,
  minReads,
  minAbundance,
  minCasePct,
  availablePipelines,
  onMaterialChange,
  onPipelineChange,
  onWindowDaysChange,
  onMinReadsChange,
  onMinAbundanceChange,
  onMinCasePctChange,
}: Readonly<NtcFiltersBarProps>) {
  const isTrana = pipeline === "trana";

  return (
    <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
      <h1 className="text-sm font-medium text-gray-900 flex-1">NTC trends</h1>

      {!isTrana && (
        <div className="flex items-center gap-1">
          {MATERIALS.map((m) => (
            <button
              key={m}
              onClick={() => onMaterialChange(m)}
              className={pillClass(material === m)}
            >
              {m}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1 border-l border-gray-100 pl-3">
        {availablePipelines.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => onPipelineChange(value)}
            className={pillClass(pipeline === value)}
          >
            {label}
          </button>
        ))}
      </div>

      {isTrana ? (
        <div className="flex items-center gap-2 border-l border-gray-100 pl-3">
          <span className="text-xs text-gray-400">Min abundance</span>
          <select
            value={minAbundance}
            onChange={(e) => onMinAbundanceChange(Number(e.target.value))}
            className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-600 bg-white focus:outline-none"
          >
            {MIN_ABUNDANCE_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="flex items-center gap-2 border-l border-gray-100 pl-3">
          <span className="text-xs text-gray-400">Min reads</span>
          <select
            value={minReads}
            onChange={(e) => onMinReadsChange(Number(e.target.value))}
            className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-600 bg-white focus:outline-none"
          >
            {MIN_READS_OPTIONS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex items-center gap-2 border-l border-gray-100 pl-3">
        <span className="text-xs text-gray-400">Min cases</span>
        <select
          value={minCasePct}
          onChange={(e) => onMinCasePctChange(Number(e.target.value))}
          className="text-xs border border-gray-200 rounded-md px-2 py-1 text-gray-600 bg-white focus:outline-none"
        >
          {MIN_CASE_PCT_OPTIONS.map((v) => (
            <option key={v} value={v}>
              {v}%
            </option>
          ))}
        </select>
      </div>

      <Link
        to="/ntc/lists"
        className="flex items-center gap-1.5 text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-500 hover:bg-gray-50 transition-colors"
      >
        <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3" />
          <path d="M5 8h6M8 5v6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
        NTC lists
      </Link>

      <div className="flex items-center gap-2 border-l border-gray-100 pl-3">
        <span className="text-xs text-gray-400">Window</span>
        {WINDOWS.map((d) => (
          <button
            key={d}
            onClick={() => onWindowDaysChange(d)}
            className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
              windowDays === d ? PILL_ACTIVE : PILL_INACTIVE
            }`}
          >
            {d}d
          </button>
        ))}
      </div>
    </div>
  );
}
