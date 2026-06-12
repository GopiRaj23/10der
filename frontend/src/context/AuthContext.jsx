import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, clearTokens, hasTokens, setTokens } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    if (!hasTokens()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      setUser(await api.get('/users/me'))
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
    const onLogout = () => setUser(null)
    window.addEventListener('tr-logout', onLogout)
    return () => window.removeEventListener('tr-logout', onLogout)
  }, [refreshUser])

  const login = useCallback(async (email, password) => {
    const tokens = await api.post('/auth/login', { email, password }, { auth: false })
    setTokens(tokens.access_token, tokens.refresh_token)
    const me = await api.get('/users/me')
    setUser(me)
    return me
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
