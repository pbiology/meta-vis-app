import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => localStorage.getItem('username'))
  const [role, setRole] = useState(() => localStorage.getItem('role') || 'reader')

  function login(username, role) {
    localStorage.setItem('username', username)
    localStorage.setItem('role',     role)
    setUser(username)
    setRole(role)
  }

  function logout() {
    localStorage.removeItem('username')
    localStorage.removeItem('role')
    setUser(null)
    setRole('reader')
  }

  return (
    <AuthContext.Provider value={{ user, role, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}