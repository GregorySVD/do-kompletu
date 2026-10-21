export const accessTokenStorageKey = 'do-kompletu-access-token'
export const refreshTokenStorageKey = 'do-kompletu-refresh-token'

type SessionExpiredListener = () => void

const sessionExpiredListeners = new Set<SessionExpiredListener>()

export function getStoredAccessToken() {
  return sessionStorage.getItem(accessTokenStorageKey)
}

export function getStoredRefreshToken() {
  return sessionStorage.getItem(refreshTokenStorageKey)
}

export function storeAccessToken(accessToken: string) {
  sessionStorage.setItem(accessTokenStorageKey, accessToken)
}

export function storeTokenPair(accessToken: string, refreshToken: string) {
  storeAccessToken(accessToken)
  sessionStorage.setItem(refreshTokenStorageKey, refreshToken)
}

export function clearStoredTokens() {
  sessionStorage.removeItem(accessTokenStorageKey)
  sessionStorage.removeItem(refreshTokenStorageKey)
}

export function expireStoredSession() {
  clearStoredTokens()
  sessionExpiredListeners.forEach((listener) => listener())
}

export function subscribeToSessionExpiration(listener: SessionExpiredListener) {
  sessionExpiredListeners.add(listener)

  return () => {
    sessionExpiredListeners.delete(listener)
  }
}
