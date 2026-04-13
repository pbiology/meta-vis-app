import { createContext, useContext, useState, useEffect } from "react";
import { getMyPreferences, updateMyPreferences } from "../api/users";

const DEFAULT_PREFERENCES = { preferred_kingdoms: ["Viruses"] };

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => localStorage.getItem("username"));
  const [role, setRole] = useState(() => localStorage.getItem("role") || "reader");
  const [preferences, setPreferencesState] = useState(DEFAULT_PREFERENCES);
  // In-memory session state: survives navigation but resets on logout / fresh login.
  // Initialized from saved preferences; updated by the taxonomy dropdown without API calls.
  const [sessionKingdoms, setSessionKingdoms] = useState(DEFAULT_PREFERENCES.preferred_kingdoms);

  // Load preferences when the app starts with an already-logged-in user
  useEffect(() => {
    if (localStorage.getItem("username")) {
      getMyPreferences()
        .then((prefs) => {
          setPreferencesState(prefs);
          setSessionKingdoms(prefs.preferred_kingdoms);
        })
        .catch(() => {});
    }
  }, []);

  async function login(username, role) {
    localStorage.setItem("username", username);
    localStorage.setItem("role", role);
    setUser(username);
    setRole(role);
    try {
      const prefs = await getMyPreferences();
      setPreferencesState(prefs);
      setSessionKingdoms(prefs.preferred_kingdoms);
    } catch {
      setPreferencesState(DEFAULT_PREFERENCES);
      setSessionKingdoms(DEFAULT_PREFERENCES.preferred_kingdoms);
    }
  }

  function logout() {
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    setUser(null);
    setRole("reader");
    setPreferencesState(DEFAULT_PREFERENCES);
    setSessionKingdoms(DEFAULT_PREFERENCES.preferred_kingdoms);
  }

  async function setPreferences(prefs) {
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

export function useAuth() {
  return useContext(AuthContext);
}
