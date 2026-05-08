interface RemoveTaxonModalProps {
  taxonName: string;
  listLabel: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function RemoveTaxonModal({
  taxonName,
  listLabel,
  busy,
  onConfirm,
  onCancel,
}: Readonly<RemoveTaxonModalProps>) {
  return (
    <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
        <p className="text-sm font-medium text-gray-900">Remove taxon?</p>
        <p className="text-xs text-gray-500">
          This will permanently remove{" "}
          <span className="italic font-medium">{taxonName.replace(/-/g, " ")}</span> from the{" "}
          {listLabel}.
        </p>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-secondary">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
          >
            {busy ? "Removing…" : "Remove"}
          </button>
        </div>
      </div>
    </div>
  );
}
