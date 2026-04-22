import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { getMyPreferences, updateMyPreferences } from "../api/users";
import type { AuthContextValue, Role, UserPreferences } from "../api/types";

const DEFAULT_PREFERENCES: UserPreferences = {
  preferred_kingdoms: ["Viruses"],
  visible_analysis_types: ["shotgun", "amplicon"],
};

const VALID_ROLES: Role[] = ["admin", "writer", "reader"];

function toRole(value: string | null): Role {
  return VALID_ROLES.includes(value as Role) ? (value as Role) : "reader";
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<string | null>(() => localStorage.getItem("username"));
  const [role, setRole] = useState<Role>(() => toRole(localStorage.getItem("role")));
  const [preferences, setPreferencesState] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  // False while the authed user's saved preferences are still being fetched.
  // Pages that filter by visible_analysis_types gate their first fetch on this
  // to avoid a stale "all types" request racing with the real one.
  const [preferencesLoaded, setPreferencesLoaded] = useState<boolean>(
    () => !localStorage.getItem("username")
  );
  // In-memory session state: survives navigation but resets on logout / fresh login.
  // Initialized from saved preferences; updated by the taxonomy dropdown without API calls.
  const [sessionKingdoms, setSessionKingdoms] = useState<string[]>(
    DEFAULT_PREFERENCES.preferred_kingdoms
  );

  // Load preferences when the app starts with an already-logged-in user
  useEffect(() => {
    if (localStorage.getItem("username")) {
      getMyPreferences()
        .then((prefs) => {
          setPreferencesState(prefs);
          setSessionKingdoms(prefs.preferred_kingdoms);
        })
        .catch(() => {})
        .finally(() => setPreferencesLoaded(true));
    }
  }, []);

  async function login(username: string, role: Role): Promise<void> {
    localStorage.setItem("username", username);
    localStorage.setItem("role", role);
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
    localStorage.removeItem("role");
    setUser(null);
    setRole("reader");
    setPreferencesState(DEFAULT_PREFERENCES);
    setSessionKingdoms(DEFAULT_PREFERENCES.preferred_kingdoms);
    setPreferencesLoaded(true);
  }

  async function setPreferences(prefs: Partial<UserPreferences>): Promise<void> {
    const saved = await updateMyPreferences(prefs);
    setPreferencesState(saved);
    // Also sync the session state so the next sample opened reflects the new saved default.
    setSessionKingdoms(saved.preferred_kingdoms);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        preferences,
        preferencesLoaded,
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
