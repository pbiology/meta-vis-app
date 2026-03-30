import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [user,  setUser]  = useState(() => localStorage.getItem('username'))
  const [role,  setRole]  = useState(() => localStorage.getItem('role') || 'reader')

  function login(accessToken, username, role) {
    localStorage.setItem('token',    accessToken)
    localStorage.setItem('username', username)
    localStorage.setItem('role',     role)
    setToken(accessToken)
    setUser(username)
    setRole(role)
  }

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
    setToken(null)
    setUser(null)
    setRole('reader')
  }

  return (
    <AuthContext.Provider value={{ token, user, role, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}