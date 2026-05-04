import { useState } from "react";
import type { CaseNote, Role } from "../../../api/types";

interface CaseCommentsProps {
  notes: CaseNote[];
  currentUser: string | null;
  role: Role;
  onAdd: (text: string) => Promise<void>;
  onDelete: (noteId: string) => Promise<void>;
}

export default function CaseComments({
  notes,
  currentUser,
  role,
  onAdd,
  onDelete,
}: CaseCommentsProps) {
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleAdd() {
    if (!draft.trim()) return;
    setSaving(true);
    try {
      await onAdd(draft);
      setDraft("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="bg-white border border-gray-100 rounded-lg overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
          Comments
        </h3>
        <span className="ml-2 text-[11px] text-gray-400 font-mono">{notes.length}</span>
      </div>

      <div className="px-4 py-3 flex flex-col gap-3">
        {notes.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-6">No comments yet.</p>
        )}
        {notes.map((note) => (
          <div key={note.id} className="bg-gray-50 rounded-lg px-3 py-2.5 flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-gray-700">{note.author}</span>
              <span className="text-gray-200">·</span>
              <span className="text-[11px] text-gray-400 font-mono">
                {note.created_at
                  ? new Date(note.created_at).toLocaleDateString("sv-SE", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : ""}
              </span>
              {(role === "admin" || note.author === currentUser) && (
                <button
                  onClick={() => onDelete(note.id)}
                  className="ml-auto text-gray-300 hover:text-red-500 transition-colors"
                  aria-label="Delete comment"
                >
                  <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
                    <path
                      d="M3 3l10 10M13 3L3 13"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              )}
            </div>
            <p className="text-xs text-gray-700 whitespace-pre-wrap m-0">{note.text}</p>
          </div>
        ))}
      </div>

      {role !== "reader" && (
        <div className="px-4 py-3 border-t border-gray-100 flex flex-col gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleAdd();
            }}
            placeholder="Write a comment…"
            rows={3}
            className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300 resize-none"
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-gray-300">⌘↵ to save</span>
            <button
              onClick={handleAdd}
              disabled={saving || !draft.trim()}
              className="px-3 py-1.5 text-xs rounded-md bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving…" : "Add comment"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
