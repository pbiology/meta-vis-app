import { Link, useParams } from "react-router-dom";
import { useSubject, useSubjectCases } from "../hooks/queries/useSubjects";
import Badge from "../components/Badge";

const SEX_LABELS: Record<string, string> = {
  F: "Female",
  M: "Male",
  X: "Other",
  unknown: "Unknown",
};

function analysisLabel(type: unknown): string {
  if (type === "shotgun") return "Shotgun";
  if (type === "amplicon") return "Amplicon";
  return "—";
}

function sexLabel(isLoading: boolean, sex?: string): string {
  if (isLoading) return "…";
  if (sex) return SEX_LABELS[sex] ?? sex;
  return "—";
}

export default function SubjectDetail() {
  const { subjectId = "" } = useParams();
  const subjectQ = useSubject(subjectId);
  const casesQ = useSubjectCases(subjectId);

  const subject = subjectQ.data;
  const cases = casesQ.data ?? [];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <Link
          to="/subjects"
          className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          ← Subjects
        </Link>
        <h1 className="text-sm font-medium text-gray-900 font-mono">{subjectId}</h1>
      </div>

      <div className="flex-1 overflow-auto p-6 flex flex-col gap-6">
        <div className="bg-white border border-gray-100 rounded-xl p-5 flex gap-10">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Subject ID</span>
            <span className="text-sm font-mono text-gray-800">{subjectId}</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Sex</span>
            <span className="text-sm text-gray-800">
              {sexLabel(subjectQ.isLoading, subject?.sex)}
            </span>
          </div>
        </div>

        <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <h2 className="text-sm font-medium text-gray-900">
              Cases <span className="text-gray-400 font-normal">({cases.length})</span>
            </h2>
          </div>

          {casesQ.isLoading && (
            <div className="flex items-center justify-center h-32 text-sm text-gray-400">
              Loading…
            </div>
          )}
          {casesQ.isError && (
            <div className="flex items-center justify-center h-32 text-sm text-red-500">
              Failed to load cases.
            </div>
          )}
          {!casesQ.isLoading && !casesQ.isError && (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr>
                  {[
                    "Case name",
                    "Date",
                    "Analysis",
                    "Platform",
                    "Samples",
                    "Status",
                    "Reviewed by",
                  ].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr
                    key={c.case_id}
                    onClick={() =>
                      window.open(`/cases/${c.case_id}`, "_blank", "noopener,noreferrer")
                    }
                    className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-700">{c.case_id}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {c.order_date ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {analysisLabel(c.analysis_type)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {c.sequencing_platform
                        ? c.sequencing_platform.charAt(0).toUpperCase() +
                          c.sequencing_platform.slice(1)
                        : "—"}
                    </td>
                    <td
                      className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap"
                      title={(c.sample_names ?? []).join(", ") || undefined}
                    >
                      {c.sample_count ?? 0} sample{(c.sample_count ?? 0) === 1 ? "" : "s"}
                      {(c.control_count ?? 0) > 0 && (
                        <span className="text-gray-300 ml-1">+{c.control_count} ctrl</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge type={c.review?.reviewed ? "reviewed" : "pending"} />
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {c.review?.reviewed_by ?? "—"}
                    </td>
                  </tr>
                ))}
                {cases.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-400">
                      No cases for this subject.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
