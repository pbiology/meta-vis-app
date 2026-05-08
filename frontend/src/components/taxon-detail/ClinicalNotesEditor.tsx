import { useEffect, useRef, useState } from "react";
import { useUpdateClinicalNotes } from "../../hooks/queries/useTaxa";
import { useAuth } from "../../context/AuthContext";

interface ClinicalNotesEditorProps {
  taxonId: number;
  initialNotes?: string | null;
  notesAuthor?: string | null;
  notesUpdatedAt?: string | null;
  canEdit: boolean;
}

export default function ClinicalNotesEditor({
  taxonId,
  initialNotes,
  notesAuthor,
  notesUpdatedAt,
  canEdit,
}: Readonly<ClinicalNotesEditorProps>) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState<string>(initialNotes ?? "");
  const [author, setAuthor] = useState<string | null>(notesAuthor ?? null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(notesUpdatedAt ?? null);
  const [error, setError] = useState<string | null>(null);
  const { user: currentUsername } = useAuth();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const updateMutation = useUpdateClinicalNotes();

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [editing]);

  async function handleSave() {
    setError(null);
    try {
      const trimmed = value.trim() || null;
      await updateMutation.mutateAsync({ taxonId, clinicalNotes: trimmed });
      if (trimmed) {
        setAuthor(currentUsername);
        setUpdatedAt(new Date().toISOString());
      } else {
        setAuthor(null);
        setUpdatedAt(null);
      }
      setEditing(false);
    } catch {
      setError("Failed to save. Please try again.");
    }
  }

  function handleCancel() {
    setValue(initialNotes ?? "");
    setEditing(false);
    setError(null);
  }

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
          Clinical notes
        </p>
        {canEdit && !editing && (
          <button
            onClick={() => setEditing(true)}
            className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
          >
            {value ? "Edit" : "Add notes"}
          </button>
        )}
      </div>
      <div className="px-4 py-3">
        {editing && (
          <div className="flex flex-col gap-2">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              rows={5}
              className="w-full text-xs text-gray-700 border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300 resize-none"
              placeholder="Add clinical context, known disease associations, relevant notes…"
            />
            {error && <p className="text-xs text-red-400">{error}</p>}
            <div className="flex gap-2 justify-end">
              <button
                onClick={handleCancel}
                className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="text-xs px-3 py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                {updateMutation.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        )}
        {!editing && value && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{value}</p>
            {author && (
              <p className="text-xs text-gray-300">
                Last updated by <span className="text-gray-400 font-medium">{author}</span>
                {updatedAt && (
                  <>
                    {" "}
                    on{" "}
                    <span className="text-gray-400">
                      {new Date(updatedAt).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </>
                )}
              </p>
            )}
          </div>
        )}
        {!editing && !value && (
          <p className="text-xs text-gray-300 italic">No clinical notes recorded.</p>
        )}
      </div>
    </section>
  );
}
