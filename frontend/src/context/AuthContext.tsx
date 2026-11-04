import {
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { getCurrentUser, loginUser, registerUser } from '../api/authApi'
import {
  clearStoredTokens,
  getStoredAccessToken,
  getStoredRefreshToken,
  storeTokenPair,
  subscribeToSessionExpiration,
} from '../auth/authSession'
import {
  getStoredSessionIdentity,
  restoreSession,
  type SessionRestoreResult,
} from '../auth/restoreSession'
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
    queryKey[0] === 'admin' ||
    queryKey[0] === 'my-activities' ||
    queryKey[0] === 'activity-photos' ||
    (queryKey[0] === 'activity-details' && queryKey[1] !== 'anonymous')
  )
}

function clearPrivateClientState(queryClient: QueryClient) {
  const privateQueryFilters = {
    predicate: (query: { queryKey: QueryKey }) =>
      isPrivateQueryKey(query.queryKey),
  }

  void queryClient.cancelQueries(privateQueryFilters, { silent: true })
  queryClient.removeQueries(privateQueryFilters)
  queryClient.getMutationCache().clear()
}

interface PendingSessionRestore {
  sessionIdentity: string | null
  promise: Promise<SessionRestoreResult>
}

let pendingSessionRestore: PendingSessionRestore | null = null

function getRestoredSession() {
  const sessionIdentity = getStoredSessionIdentity()

  if (pendingSessionRestore?.sessionIdentity === sessionIdentity) {
    return pendingSessionRestore.promise
  }

  const scopedPromise: Promise<SessionRestoreResult> = restoreSession().finally(
    () => {
      if (pendingSessionRestore?.promise === scopedPromise) {
        pendingSessionRestore = null
      }
    },
  )

  pendingSessionRestore = { sessionIdentity, promise: scopedPromise }
  return scopedPromise
}

export function AuthProvider({ children }: AuthProviderProps) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [sessionRestoreError, setSessionRestoreError] = useState(false)
  const [isSessionRestoreRetrying, setIsSessionRestoreRetrying] =
    useState(false)
  const profileUpdateVersionRef = useRef(0)

  function applySessionRestoreResult(result: SessionRestoreResult) {
    setIsSessionRestoreRetrying(false)

    if (result.status === 'stale') {
      return
    }

    profileUpdateVersionRef.current += 1

    if (result.status === 'error') {
      setUser(null)
      setSessionRestoreError(true)
      setIsLoading(true)
      return
    }

    setUser(result.user)
    setSessionRestoreError(false)
    setIsLoading(false)
  }

  useEffect(
    () =>
      subscribeToSessionExpiration(() => {
        profileUpdateVersionRef.current += 1
        clearPrivateClientState(queryClient)
        setUser(null)
        setSessionRestoreError(false)
        setIsSessionRestoreRetrying(false)
        setIsLoading(false)
      }),
    [queryClient],
  )

  useEffect(() => {
    let isActive = true

    void getRestoredSession().then((result) => {
      if (isActive) {
        applySessionRestoreResult(result)
      }
    })

    return () => {
      isActive = false
    }
  }, [])

  async function login(values: LoginFormValues) {
    const tokens = await loginUser(values)
    profileUpdateVersionRef.current += 1
    const loginProfileUpdateVersion = profileUpdateVersionRef.current
    clearPrivateClientState(queryClient)
    storeTokenPair(tokens.access_token, tokens.refresh_token)
    const loginSessionIdentity = getStoredSessionIdentity()
    setUser(null)
    setSessionRestoreError(false)
    setIsSessionRestoreRetrying(false)
    setIsLoading(true)

    try {
      const loggedInUser = await getCurrentUser()

      if (
        profileUpdateVersionRef.current !== loginProfileUpdateVersion ||
        getStoredSessionIdentity() !== loginSessionIdentity
      ) {
        return
      }

      setUser(loggedInUser)
      setIsLoading(false)
    } catch (error) {
      if (
        profileUpdateVersionRef.current !== loginProfileUpdateVersion ||
        getStoredSessionIdentity() !== loginSessionIdentity
      ) {
        throw error
      }

      clearPrivateClientState(queryClient)
      setUser(null)

      if (getStoredAccessToken() || getStoredRefreshToken()) {
        setSessionRestoreError(true)
        setIsLoading(true)
      } else {
        setSessionRestoreError(false)
        setIsLoading(false)
      }

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
    profileUpdateVersionRef.current += 1
    clearStoredTokens()
    clearPrivateClientState(queryClient)
    setUser(null)
    setSessionRestoreError(false)
    setIsSessionRestoreRetrying(false)
    setIsLoading(false)
  }

  function retrySessionRestore() {
    if (isSessionRestoreRetrying) {
      return
    }

    setIsSessionRestoreRetrying(true)
    void getRestoredSession().then(applySessionRestoreResult)
  }

  const refreshUser = useCallback(async () => {
    const sessionIdentity = getStoredSessionIdentity()

    if (!sessionIdentity) {
      return
    }

    const profileUpdateVersion = profileUpdateVersionRef.current + 1
    profileUpdateVersionRef.current = profileUpdateVersion
    const refreshedUser = await getCurrentUser()

    if (
      profileUpdateVersionRef.current !== profileUpdateVersion ||
      getStoredSessionIdentity() !== sessionIdentity
    ) {
      return
    }

    setUser((currentUser) =>
      currentUser?.id === refreshedUser.id ? refreshedUser : currentUser,
    )
  }, [])

  function syncUserProfile(profile: UserProfile) {
    profileUpdateVersionRef.current += 1
    setUser((currentUser) =>
      currentUser?.id === profile.id ? profile : currentUser,
    )
  }

  const value = {
    user,
    isAuthenticated: user !== null,
    isLoading,
    isSessionRestoreRetrying,
    sessionRestoreError,
    login,
    register,
    logout,
    retrySessionRestore,
    refreshUser,
    syncUserProfile,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
