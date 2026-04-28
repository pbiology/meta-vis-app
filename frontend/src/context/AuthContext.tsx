import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { getMyPreferences, updateMyPreferences } from "../api/users";
import { getMe } from "../api/auth";
import type { AuthContextValue, Role, UserPreferences } from "../api/types";

const DEFAULT_PREFERENCES: UserPreferences = {
  preferred_kingdoms: ["Viruses"],
  visible_analysis_types: ["shotgun", "amplicon"],
};

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<string | null>(() => localStorage.getItem("username"));
  // Role is never read from localStorage — always sourced from the server.
  const [role, setRole] = useState<Role>("reader");
  const [preferences, setPreferencesState] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [preferencesLoaded, setPreferencesLoaded] = useState<boolean>(
    () => !localStorage.getItem("username")
  );
  // True while the initial /auth/me call is in-flight. Prevents rendering
  // the protected shell with a stale/spoofed role from localStorage.
  const [authLoading, setAuthLoading] = useState<boolean>(() => !!localStorage.getItem("username"));
  const [sessionKingdoms, setSessionKingdoms] = useState<string[]>(
    DEFAULT_PREFERENCES.preferred_kingdoms
  );

  // On startup with a stored session: verify the token and fetch authoritative role + prefs.
  useEffect(() => {
    if (!localStorage.getItem("username")) return;
    Promise.all([getMe(), getMyPreferences()])
      .then(([me, prefs]) => {
        setRole(me.role);
        setPreferencesState(prefs);
        setSessionKingdoms(prefs.preferred_kingdoms);
      })
      .catch(() => {
        // Token expired or invalid — clear the stale session.
        logout();
      })
      .finally(() => {
        setAuthLoading(false);
        setPreferencesLoaded(true);
      });
  }, []);

  async function login(username: string, role: Role): Promise<void> {
    localStorage.setItem("username", username);
    // Role is received directly from the server LoginResponse — no localStorage.
    setUser(username);
    setRole(role);
    setPreferencesLoaded(false);
    try {
      const prefs = await getMyPreferences();
      setPreferencesState(prefs);
      setSessionKingdoms(prefs.preferred_kingdoms);
    } catch {
      setPreferencesState(DEFAULT_PREFERENCES);
      setSessionKingdoms(DEFAULT_PREFERENCES.preferred_kingdoms);
    } finally {
      setPreferencesLoaded(true);
    }
  }

  function logout(): void {
    localStorage.removeItem("username");
    setUser(null);
    setRole("reader");
    setPreferencesState(DEFAULT_PREFERENCES);
    setSessionKingdoms(DEFAULT_PREFERENCES.preferred_kingdoms);
    setPreferencesLoaded(true);
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
        authLoading,
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
