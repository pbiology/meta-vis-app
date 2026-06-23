// Centralised OIDC user manager. A single shared instance is used by both
// the React provider (in main.tsx) and the axios client (which reads the
// current access token to attach as a Bearer header).
//
// Storing tokens in localStorage is acceptable here because the SPA is the
// public OIDC client — there is no httpOnly-cookie option without an
// intermediary backend, and CSRF protection isn't needed for Bearer headers.

import { UserManager, WebStorageStateStore } from "oidc-client-ts";

// Runtime env vars injected by docker-entrypoint.d/10-inject-env.sh take
// precedence over values baked in at build time.
const runtimeEnv = (globalThis as unknown as { __ENV__?: Record<string, string> }).__ENV__ ?? {};
const runtimeOr = (key: string) => runtimeEnv[key] || (import.meta.env[key] as string);

const authority = runtimeOr("VITE_OIDC_AUTHORITY");
const clientId = runtimeOr("VITE_OIDC_CLIENT_ID");

if (!authority || !clientId) {
  // Surface misconfiguration loudly during dev — the only remedy is to set
  // the env vars and restart Vite.
  console.error("OIDC env vars missing: VITE_OIDC_AUTHORITY / VITE_OIDC_CLIENT_ID");
}

export const userManager = new UserManager({
  authority,
  client_id: clientId,
  redirect_uri:
    runtimeOr("VITE_OIDC_REDIRECT_URI") ??
    `${globalThis.location.origin}/auth/callback`,
  post_logout_redirect_uri:
    runtimeOr("VITE_OIDC_POST_LOGOUT_REDIRECT_URI") ??
    globalThis.location.origin,
  userStore: new WebStorageStateStore({ store: globalThis.localStorage }),
  monitorSession: false,
});

export const oidcConfig = {
  userManager,
  onSigninCallback: () => {
    // Strip the ?code=… &state=… params from the URL after a successful login
    // so a refresh doesn't try to redeem the code a second time.
    globalThis.history.replaceState({}, document.title, globalThis.location.pathname);
  },
};
