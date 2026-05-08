export type BlastStatus = "blasting" | "error";

interface BlastModalProps {
  status: BlastStatus;
  error: string | null;
  onClose: () => void;
}

export default function BlastModal({ status, error, onClose }: Readonly<BlastModalProps>) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-2xl shadow-xl px-8 py-7 max-w-sm w-full mx-4 flex flex-col gap-4">
        {status === "blasting" && (
          <>
            <div className="flex items-center gap-3">
              <svg
                className="w-5 h-5 animate-spin text-blue-500 flex-shrink-0"
                viewBox="0 0 16 16"
                fill="none"
              >
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeDasharray="28"
                  strokeDashoffset="10"
                />
              </svg>
              <p className="text-sm font-medium text-gray-800">Submitting to NCBI BLAST…</p>
            </div>
            <p className="text-xs text-gray-400">This can take up to 30 seconds.</p>
          </>
        )}
        {status === "error" && (
          <>
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-red-400 flex-shrink-0" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" />
                <path
                  d="M8 5v3M8 10.5v.5"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
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
  );
}
