import { Link } from "react-router-dom";
import type { NtcContaminantAlert } from "../../api/types";

interface NtcContaminantBannerProps {
  alerts: NtcContaminantAlert[];
}

export default function NtcContaminantBanner({ alerts }: Readonly<NtcContaminantBannerProps>) {
  if (alerts.length === 0) return null;
  return (
    <div className="bg-orange-50 border border-orange-200 rounded-xl px-4 py-3 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <svg className="w-3.5 h-3.5 text-orange-500 flex-shrink-0" viewBox="0 0 16 16" fill="none">
          <path
            d="M8 3a3 3 0 0 1 3 3v1.5h.5a1 1 0 0 1 1 1V13a1 1 0 0 1-1 1H4.5a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1H5V6a3 3 0 0 1 3-3z"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinejoin="round"
          />
          <circle cx="8" cy="10.5" r="0.75" fill="currentColor" />
        </svg>
        <span className="text-xs font-medium text-orange-700">
          Known contaminant{alerts.length !== 1 ? "s" : ""} detected in NTCs
        </span>
        <Link
          to="/ntc/lists"
          className="ml-auto text-xs text-orange-500 hover:text-orange-700 underline underline-offset-2"
        >
          Manage lists
        </Link>
      </div>
      {alerts.map((alert) => (
        <div key={alert.taxon_id} className="flex items-center gap-2 text-xs text-orange-700">
          <span className="italic">{alert.taxon_name.replace(/-/g, " ")}</span>
          <span className="text-orange-400">·</span>
          <span className="text-orange-500">
            {alert.case_count} case{alert.case_count !== 1 ? "s" : ""}
          </span>
          <span className="text-orange-400">·</span>
          <span className="text-orange-400">&gt; {alert.min_reads} reads threshold</span>
        </div>
      ))}
    </div>
  );
}
