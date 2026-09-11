import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { requestToken, revokeToken } from '../api/authApi'
import {
  clearStoredAuth,
  getStoredExpiry,
  getStoredToken,
  isStoredTokenExpired,
  onAuthChange,
  setStoredAuth,
  type StoredAuth,
} from '../api/http'
import { AuthContext } from './useAuth'

function readStoredAuth(): StoredAuth | null {
  const token = getStoredToken()
  if (!token) {
    return null
  }
  if (isStoredTokenExpired()) {
    clearStoredAuth()
    return null
  }
  return { token, expiry: getStoredExpiry() }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<StoredAuth | null>(() => readStoredAuth())

  useEffect(
    () =>
      onAuthChange((next) => {
        setAuth(next)
      }),
    [],
  )

  const login = useCallback(async (email: string, password: string) => {
    const data = await requestToken(email, password)
    setStoredAuth({ token: data.token, expiry: data.expiry })
  }, [])

  const logout = useCallback(() => {
    if (auth?.token) {
      revokeToken(auth.token)
    }
    clearStoredAuth()
    setAuth(null)
  }, [auth])

  const value = useMemo(
    () => ({
      token: auth?.token ?? null,
      expiry: auth?.expiry ?? null,
      isAuthenticated: auth !== null,
      login,
      logout,
    }),
    [auth, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
