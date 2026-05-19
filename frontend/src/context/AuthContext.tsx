import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useAuth as useOidcAuth } from "react-oidc-context";
import { getMyPreferences, updateMyPreferences } from "../api/users";
import type { AuthContextValue, Role, UserPreferences } from "../api/types";

const DEFAULT_PREFERENCES: UserPreferences = {
  preferred_kingdoms: ["Viruses"],
  visible_analysis_types: ["shotgun", "amplicon"],
};

const ROLE_PRIORITY: Role[] = ["admin", "writer", "reader"];

function deriveRole(realmRoles: string[] | undefined): Role {
  const lowered = new Set((realmRoles ?? []).map((r) => r.toLowerCase()));
  for (const role of ROLE_PRIORITY) {
    if (lowered.has(role)) return role;
  }
  return "reader";
}

// Client roles are emitted in the access token (not the ID token), so we
// decode its payload directly. No signature check here — the backend is the
// authority on whether a token is valid; the frontend only uses claims for
// UI gating.
const ROLE_CLIENT =
  (import.meta.env.VITE_OIDC_ROLE_CLIENT as string | undefined) ||
  (import.meta.env.VITE_OIDC_CLIENT_ID as string);

function clientRolesFromAccessToken(token: string | undefined): string[] {
  if (!token) return [];
  try {
    const payload = token.split(".")[1];
    const padded = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = JSON.parse(atob(padded));
    const access = json?.resource_access?.[ROLE_CLIENT];
    return (access?.roles as string[] | undefined) ?? [];
  } catch {
    return [];
  }
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const oidc = useOidcAuth();

  const profile = oidc.user?.profile as { preferred_username?: string } | undefined;
  const user = oidc.isAuthenticated ? (profile?.preferred_username ?? null) : null;
  const role = deriveRole(clientRolesFromAccessToken(oidc.user?.access_token));

  const [preferences, setPreferencesState] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [preferencesLoaded, setPreferencesLoaded] = useState<boolean>(false);
  const [sessionKingdoms, setSessionKingdoms] = useState<string[]>(
    DEFAULT_PREFERENCES.preferred_kingdoms
  );

  // Fetch preferences once we have an authenticated session. The OIDC
  // provider may flip isAuthenticated multiple times during a silent refresh,
  // so we guard on user identity to avoid refetching needlessly.
  useEffect(() => {
    if (!oidc.isAuthenticated) {
      setPreferencesState(DEFAULT_PREFERENCES);
      setSessionKingdoms(DEFAULT_PREFERENCES.preferred_kingdoms);
      setPreferencesLoaded(false);
      return;
    }
    let cancelled = false;
    getMyPreferences()
      .then((prefs) => {
        if (cancelled) return;
        setPreferencesState(prefs);
        setSessionKingdoms(prefs.preferred_kingdoms);
      })
      .catch(() => {
        if (cancelled) return;
        setPreferencesState(DEFAULT_PREFERENCES);
        setSessionKingdoms(DEFAULT_PREFERENCES.preferred_kingdoms);
      })
      .finally(() => {
        if (!cancelled) setPreferencesLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [oidc.isAuthenticated, oidc.user?.profile.sub]);

  async function login(): Promise<void> {
    await oidc.signinRedirect();
  }

  function logout(): void {
    oidc.signoutRedirect().catch((err) => console.error("signoutRedirect failed", err));
  }

  async function setPreferences(prefs: Partial<UserPreferences>): Promise<void> {
    const saved = await updateMyPreferences(prefs);
    setPreferencesState(saved);
    setSessionKingdoms(saved.preferred_kingdoms);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        preferences,
        preferencesLoaded,
        authLoading: oidc.isLoading,
        sessionKingdoms,
        setSessionKingdoms,
        login,
        logout,
        setPreferences,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
