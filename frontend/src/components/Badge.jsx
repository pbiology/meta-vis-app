export default function Badge({ type }) {
  const variants = {
    reviewed: "bg-green-50 text-green-700",
    pending: "bg-amber-50 text-amber-700",
    sample: "bg-blue-50 text-blue-700",
    negative_ctrl: "bg-gray-100 text-gray-600",
    positive_ctrl: "bg-purple-50 text-purple-700",
  };

  const labels = {
    reviewed: "Reviewed",
    pending: "Pending",
    sample: "sample",
    negative_ctrl: "neg ctrl",
    positive_ctrl: "pos ctrl",
  };

  const dots = {
    reviewed: "bg-green-500",
    pending: "bg-amber-500",
  };

  const cls = variants[type] || "bg-gray-100 text-gray-600";
  const label = labels[type] || type;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}
    >
      {dots[type] && <span className={`w-1.5 h-1.5 rounded-full ${dots[type]}`} />}
      {label}
    </span>
  );
}
