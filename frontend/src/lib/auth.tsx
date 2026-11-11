import { createContext, useContext, useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { api, TOKEN_KEY, type LoginResponse } from './api'

interface AuthState {
  token: string | null
  login: (username: string, password: string, industry?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))

  /** `industry`: switch to it on success (the login page's industry tabs); omitted = keep the current one. */
  async function login(username: string, password: string, industry?: string) {
    const { data } = await api.post<LoginResponse>('/auth/login', { username, password, ...(industry ? { industry } : {}) })
    localStorage.setItem(TOKEN_KEY, data.access_token)
    setToken(data.access_token)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
  }

  return <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  return token ? children : <Navigate to="/login" replace />
}
