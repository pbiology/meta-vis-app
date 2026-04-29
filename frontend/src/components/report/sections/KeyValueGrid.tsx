import type { ReactNode } from "react";

export interface KvPair {
  label: string;
  value: ReactNode;
  // When true, value uses a tabular/mono font for ids and numbers.
  mono?: boolean;
}

interface KeyValueGridProps {
  pairs: KvPair[];
}

const DASH = "—";

// Two-column key/value grid with dotted leaders between label and value, mirroring
// the prototype's clinical layout. Empty values render as an em-dash so missing
// fields are visible at a glance.
export default function KeyValueGrid({ pairs }: Readonly<KeyValueGridProps>) {
  return (
    <dl className="report-kv-grid">
      {pairs.map(({ label, value, mono }) => {
        const display = value === null || value === undefined || value === "" ? DASH : value;
        return (
          <div key={label} className="report-kv-row">
            <dt className="report-kv-label">{label}</dt>
            <dd className={`report-kv-value${mono ? " report-mono" : ""}`}>{display}</dd>
          </div>
        );
      })}
    </dl>
  );
}
