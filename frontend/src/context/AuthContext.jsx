import { createContext, useContext, useState, useEffect } from "react";
import { getMyPreferences, updateMyPreferences } from "../api/users";

const DEFAULT_PREFERENCES = { preferred_kingdoms: ["Viruses"] };

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => localStorage.getItem("username"));
  const [role, setRole] = useState(() => localStorage.getItem("role") || "reader");
  const [preferences, setPreferencesState] = useState(DEFAULT_PREFERENCES);

  // Load preferences when the app starts with an already-logged-in user
  useEffect(() => {
    if (localStorage.getItem("username")) {
      getMyPreferences()
        .then(setPreferencesState)
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
    } catch {
      setPreferencesState(DEFAULT_PREFERENCES);
    }
  }

  function logout() {
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    setUser(null);
    setRole("reader");
    setPreferencesState(DEFAULT_PREFERENCES);
  }

  async function setPreferences(prefs) {
    const saved = await updateMyPreferences(prefs);
    setPreferencesState(saved);
  }

  return (
    <AuthContext.Provider value={{ user, role, preferences, login, logout, setPreferences }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
