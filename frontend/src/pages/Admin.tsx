import { useAuth } from "../context/AuthContext";

// User identity is now owned by Keycloak. This page used to host inline
// user CRUD; it now points administrators at the Keycloak admin console
// (mounted alongside the dev stack — see docker-compose.keycloak.yml).
//
// The realm name is hard-coded because the SPA only ever talks to one realm,
// and we already commit the URL into the Vite env (VITE_OIDC_AUTHORITY).
const KC_AUTHORITY = import.meta.env.VITE_OIDC_AUTHORITY as string | undefined;

function adminConsoleUrl(): string | null {
  if (!KC_AUTHORITY) return null;
  // Strip the trailing "/realms/<realm>" off the authority and re-append the
  // admin console path so we always derive from the same env value.
  try {
    const url = new URL(KC_AUTHORITY);
    const match = /^(.*)\/realms\/([^/]+)\/?$/.exec(url.pathname);
    if (!match) return null;
    const [, prefix, realm] = match;
    url.pathname = `${prefix}/admin/${realm}/console/`;
    return url.toString();
  } catch {
    return null;
  }
}

export default function Admin() {
  const { role } = useAuth();
  const consoleUrl = adminConsoleUrl();

  if (role !== "admin") {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        You don&apos;t have permission to view this page.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">User management</h1>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-xl bg-white border border-gray-100 rounded-xl p-6">
          <p className="text-sm text-gray-700">
            Users, roles, and passwords are managed in Keycloak. Open the realm admin console to add
            or change users.
          </p>
          {consoleUrl ? (
            <a
              href={consoleUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-4 px-4 py-2 text-sm font-medium bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              Open Keycloak admin console
            </a>
          ) : (
            <p className="mt-4 text-xs text-red-600">
              VITE_OIDC_AUTHORITY is not configured — cannot derive the admin console URL.
            </p>
          )}
          <p className="mt-6 text-xs text-gray-500">
            Realm roles <span className="font-mono">reader</span>,{" "}
            <span className="font-mono">writer</span>, and <span className="font-mono">admin</span>{" "}
            map directly to access in this app.
          </p>
        </div>
      </div>
    </div>
  );
}
