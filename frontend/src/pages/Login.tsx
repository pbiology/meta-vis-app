import { useEffect, useRef } from "react";
import { useAuth as useOidcAuth } from "react-oidc-context";

// Login is delegated to Keycloak via the OIDC Authorization Code + PKCE flow.
// We call signinRedirect() directly on the OIDC hook (not via our wrapper
// context) so the function identity stays stable across renders — otherwise
// the effect would refire each render and queue redirects faster than the
// browser can navigate, freezing the tab.
export default function Login() {
  const oidc = useOidcAuth();
  const triggered = useRef(false);

  useEffect(() => {
    if (oidc.isLoading || oidc.isAuthenticated || triggered.current) return;
    triggered.current = true;
    void oidc.signinRedirect();
  }, [oidc.isLoading, oidc.isAuthenticated, oidc.signinRedirect]);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-lg font-medium text-gray-900 tracking-tight">meta-vis</h1>
        <p className="text-sm text-gray-400 mt-1">
          {oidc.error ? `Sign-in failed: ${oidc.error.message}` : "Redirecting to sign in…"}
        </p>
        <button
          onClick={() => {
            triggered.current = true;
            void oidc.signinRedirect();
          }}
          className="mt-6 px-4 py-2 text-sm font-medium bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors"
        >
          Sign in
        </button>
      </div>
    </div>
  );
}
