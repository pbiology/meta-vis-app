import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import NtcIgnoreListPanel from "../components/ntc/NtcIgnoreListPanel";
import NtcContaminantsPanel from "../components/ntc/NtcContaminantsPanel";

export default function NtcListsPage() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const canEdit = role !== "reader";
  const canDelete = role === "admin";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate("/ntc")}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path
              d="M10 3L5 8l5 5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          NTC trends
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 flex-1">NTC lists</h1>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">
        <NtcIgnoreListPanel canEdit={canEdit} canDelete={canDelete} />
        <NtcContaminantsPanel canEdit={canEdit} canDelete={canDelete} />
      </div>
    </div>
  );
}
