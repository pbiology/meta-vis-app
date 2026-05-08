import { useState } from "react";
import {
  useCreateUser,
  useDeleteUser,
  useUpdateUserRole,
  useUsers,
} from "../hooks/queries/useUsers";
import type { Role } from "../api/types";
import { axiosErrorDetail } from "../utils/axiosError";

const ROLES: Role[] = ["reader", "writer", "admin"];

const ROLE_STYLES: Record<Role, string> = {
  admin: "bg-purple-50 text-purple-700",
  writer: "bg-blue-50 text-blue-700",
  reader: "bg-gray-100 text-gray-600",
};

export default function Admin() {
  const usersQ = useUsers();
  const updateRoleMutation = useUpdateUserRole();
  const createMutation = useCreateUser();
  const deleteMutation = useDeleteUser();

  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPass, setNewPass] = useState("");
  const [newRole, setNewRole] = useState<Role>("reader");
  const [addError, setAddError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const users = usersQ.data ?? [];

  async function handleRoleChange(username: string, role: Role) {
    try {
      await updateRoleMutation.mutateAsync({ username, role });
    } catch {
      alert("Failed to update role.");
    }
  }

  async function handleAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setAddError(null);
    try {
      await createMutation.mutateAsync({
        username: newName.trim(),
        password: newPass,
        role: newRole,
      });
      setNewName("");
      setNewPass("");
      setNewRole("reader");
      setShowAdd(false);
    } catch (err) {
      setAddError(axiosErrorDetail(err, "Failed to create user."));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget);
      setDeleteTarget(null);
    } catch {
      alert("Failed to delete user.");
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">User management</h1>
        <button onClick={() => setShowAdd(true)} className="btn-primary">
          + Add user
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {usersQ.isLoading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {usersQ.isError && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">
            Failed to load users.
          </div>
        )}
        {!usersQ.isLoading && !usersQ.isError && (
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr>
                {["Username", "Title", "Reviews", "Role", ""].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u._id} className="border-b border-gray-50">
                  <td className="px-4 py-3 text-xs font-mono text-gray-700">{u.username}</td>
                  <td className="px-4 py-3 text-xs text-gray-400 italic">{u.reviewer_title}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 tabular-nums">{u.reviews}</td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.username, e.target.value as Role)}
                      className={`text-xs px-2 py-1 rounded-full border-0 font-medium cursor-pointer outline-none ${ROLE_STYLES[u.role] ?? ROLE_STYLES.reader}`}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r.charAt(0).toUpperCase() + r.slice(1)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setDeleteTarget(u.username)}
                      className="text-xs text-gray-300 hover:text-red-500 transition-colors"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showAdd && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900">Add user</p>
            <form onSubmit={handleAdd} className="flex flex-col gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Username</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  className="w-full text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-300"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Password</label>
                <input
                  type="password"
                  value={newPass}
                  onChange={(e) => setNewPass(e.target.value)}
                  required
                  className="w-full text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-300"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Role</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as Role)}
                  className="w-full text-xs border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-300 bg-white"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r.charAt(0).toUpperCase() + r.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              {addError && <p className="text-xs text-red-500">{addError}</p>}
              <div className="flex gap-2 justify-end pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setShowAdd(false);
                    setAddError(null);
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="btn-primary disabled:opacity-50"
                >
                  {createMutation.isPending ? "Adding…" : "Add user"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900">Remove user?</p>
            <p className="text-xs text-gray-500">
              This will permanently delete{" "}
              <span className="font-medium font-mono">{deleteTarget}</span>. This cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteTarget(null)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="btn-primary disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Removing…" : "Remove user"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
