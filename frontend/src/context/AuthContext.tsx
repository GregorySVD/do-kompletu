import { useEffect, useState, type ReactNode } from 'react'
import {
  getCurrentUser,
  loginUser,
  refreshAccessToken,
  registerUser,
} from '../api/authApi'
import { accessTokenStorageKey, refreshTokenStorageKey } from '../api/apiClient'
import type {
  LoginFormValues,
  RegisterFormValues,
  UserProfile,
} from '../types/auth'
import { AuthContext } from './auth'

interface AuthProviderProps {
  children: ReactNode
}

function clearStoredTokens() {
  sessionStorage.removeItem(accessTokenStorageKey)
  sessionStorage.removeItem(refreshTokenStorageKey)
}

async function restoreSession(): Promise<UserProfile | null> {
  const accessToken = sessionStorage.getItem(accessTokenStorageKey)

  if (!accessToken) {
    clearStoredTokens()
    return null
  }

  try {
    return await getCurrentUser()
  } catch {
    const refreshToken = sessionStorage.getItem(refreshTokenStorageKey)

    if (!refreshToken) {
      clearStoredTokens()
      return null
    }

    try {
      const refreshedToken = await refreshAccessToken(refreshToken)
      sessionStorage.setItem(accessTokenStorageKey, refreshedToken.access_token)
      return await getCurrentUser()
    } catch {
      clearStoredTokens()
      return null
    }
  }
}

let pendingSessionRestore: Promise<UserProfile | null> | null = null

function getRestoredSession() {
  pendingSessionRestore ??= restoreSession()
  return pendingSessionRestore
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let isActive = true

    void getRestoredSession().then((restoredUser) => {
      if (isActive) {
        setUser(restoredUser)
        setIsLoading(false)
      }
    })

    return () => {
      isActive = false
    }
  }, [])

  async function login(values: LoginFormValues) {
    const tokens = await loginUser(values)
    sessionStorage.setItem(accessTokenStorageKey, tokens.access_token)
    sessionStorage.setItem(refreshTokenStorageKey, tokens.refresh_token)

    try {
      setUser(await getCurrentUser())
    } catch (error) {
      clearStoredTokens()
      setUser(null)
      throw error
    }
  }

  async function register(values: RegisterFormValues) {
    await registerUser({
      display_name: values.display_name,
      email: values.email,
      password: values.password,
    })
  }

  function logout() {
    clearStoredTokens()
    setUser(null)
  }

  async function refreshUser() {
    setUser(await getCurrentUser())
  }

  const value = {
    user,
    isAuthenticated: user !== null,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
