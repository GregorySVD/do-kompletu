import {
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { getCurrentUser, loginUser, registerUser } from '../api/authApi'
import {
  clearStoredTokens,
  getStoredAccessToken,
  getStoredRefreshToken,
  storeTokenPair,
  subscribeToSessionExpiration,
} from '../auth/authSession'
import type {
  LoginFormValues,
  RegisterFormValues,
  UserProfile,
} from '../types/auth'
import { AuthContext } from './auth'

interface AuthProviderProps {
  children: ReactNode
}

function isPrivateQueryKey(queryKey: QueryKey) {
  return (
    queryKey[0] === 'my-activities' ||
    (queryKey[0] === 'activity-details' && queryKey[1] !== 'anonymous')
  )
}

function clearPrivateClientState(queryClient: QueryClient) {
  queryClient.removeQueries({
    predicate: (query) => isPrivateQueryKey(query.queryKey),
  })
  queryClient.getMutationCache().clear()
}

async function restoreSession(): Promise<UserProfile | null> {
  if (!getStoredAccessToken() && !getStoredRefreshToken()) {
    return null
  }

  try {
    return await getCurrentUser()
  } catch {
    return null
  }
}

let pendingSessionRestore: Promise<UserProfile | null> | null = null

function getRestoredSession() {
  pendingSessionRestore ??= restoreSession().finally(() => {
    pendingSessionRestore = null
  })
  return pendingSessionRestore
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(
    () =>
      subscribeToSessionExpiration(() => {
        clearPrivateClientState(queryClient)
        setUser(null)
        setIsLoading(false)
      }),
    [queryClient],
  )

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
    storeTokenPair(tokens.access_token, tokens.refresh_token)

    try {
      const loggedInUser = await getCurrentUser()
      clearPrivateClientState(queryClient)
      setUser(loggedInUser)
    } catch (error) {
      clearPrivateClientState(queryClient)
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
    clearPrivateClientState(queryClient)
    setUser(null)
  }

  async function refreshUser() {
    setUser(await getCurrentUser())
  }

  function syncUserProfile(profile: UserProfile) {
    setUser(profile)
  }

  const value = {
    user,
    isAuthenticated: user !== null,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
    syncUserProfile,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
