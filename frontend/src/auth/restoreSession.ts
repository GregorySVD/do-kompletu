import { getCurrentUser } from '../api/authApi'
import type { UserProfile } from '../types/auth'
import { getStoredAccessToken, getStoredRefreshToken } from './authSession'

export type SessionRestoreResult =
  | { status: 'resolved'; user: UserProfile | null }
  | { status: 'error' }
  | { status: 'stale' }

export function getStoredSessionIdentity() {
  return getStoredRefreshToken() ?? getStoredAccessToken()
}

export async function restoreSession(): Promise<SessionRestoreResult> {
  const sessionIdentity = getStoredSessionIdentity()

  if (!sessionIdentity) {
    return { status: 'resolved', user: null }
  }

  try {
    const user = await getCurrentUser()

    if (getStoredSessionIdentity() !== sessionIdentity) {
      return { status: 'stale' }
    }

    return { status: 'resolved', user }
  } catch {
    if (!getStoredAccessToken() && !getStoredRefreshToken()) {
      return { status: 'resolved', user: null }
    }

    if (getStoredSessionIdentity() !== sessionIdentity) {
      return { status: 'stale' }
    }

    return { status: 'error' }
  }
}
