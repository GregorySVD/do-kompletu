import axios, { type InternalAxiosRequestConfig } from 'axios'
import {
  accessTokenStorageKey,
  expireStoredSession,
  getStoredAccessToken,
  getStoredRefreshToken,
  refreshTokenStorageKey,
  storeAccessToken,
} from '../auth/authSession'
import { requestAccessTokenRefresh } from './authRefreshApi'

export { accessTokenStorageKey, refreshTokenStorageKey }

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
  _refreshToken?: string
  _sessionRefreshToken?: string | null
}

interface PendingRefresh {
  refreshToken: string
  promise: Promise<string>
}

const authEndpointsWithoutRefresh = new Set([
  '/api/v1/auth/login',
  '/api/v1/auth/register',
  '/api/v1/auth/refresh',
  '/api/v1/auth/token',
])

let pendingAccessTokenRefresh: PendingRefresh | null = null

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

apiClient.interceptors.request.use((config) => {
  const requestConfig = config as RetryableRequestConfig
  const accessToken = getStoredAccessToken()
  const refreshToken = getStoredRefreshToken()

  if (requestConfig._sessionRefreshToken === undefined) {
    requestConfig._sessionRefreshToken = refreshToken
  } else if (requestConfig._sessionRefreshToken !== refreshToken) {
    throw createStaleSessionRequestError(requestConfig)
  }

  if (accessToken) {
    requestConfig.headers.Authorization = `Bearer ${accessToken}`
  }

  return requestConfig
})

function createStaleSessionRequestError(config?: RetryableRequestConfig) {
  return new axios.CanceledError(
    'Request canceled because the authentication session changed',
    config,
  )
}

function isAuthEndpointWithoutRefresh(url: string | undefined) {
  if (!url) {
    return false
  }

  const pathname = new URL(url, 'http://localhost').pathname.replace(/\/$/, '')
  return authEndpointsWithoutRefresh.has(pathname)
}

function refreshAccessTokenSingleFlight(refreshToken: string) {
  if (pendingAccessTokenRefresh?.refreshToken === refreshToken) {
    return pendingAccessTokenRefresh.promise
  }

  const refreshRequest = requestAccessTokenRefresh(refreshToken)
    .then(({ access_token: accessToken }) => {
      if (getStoredRefreshToken() !== refreshToken) {
        throw createStaleSessionRequestError()
      }

      storeAccessToken(accessToken)
      return accessToken
    })
    .catch((error: unknown) => {
      if (
        axios.isAxiosError(error) &&
        (error.response?.status === 401 || error.response?.status === 422) &&
        getStoredRefreshToken() === refreshToken
      ) {
        expireStoredSession()
      }

      throw error
    })

  const scopedPromise: Promise<string> = refreshRequest.finally(() => {
    if (pendingAccessTokenRefresh?.promise === scopedPromise) {
      pendingAccessTokenRefresh = null
    }
  })

  pendingAccessTokenRefresh = {
    refreshToken,
    promise: scopedPromise,
  }

  return scopedPromise
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || error.response?.status !== 401) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as RetryableRequestConfig | undefined

    if (!originalRequest || isAuthEndpointWithoutRefresh(originalRequest.url)) {
      return Promise.reject(error)
    }

    if (originalRequest._sessionRefreshToken !== getStoredRefreshToken()) {
      return Promise.reject(createStaleSessionRequestError(originalRequest))
    }

    if (originalRequest._retry) {
      if (
        originalRequest._refreshToken &&
        getStoredRefreshToken() === originalRequest._refreshToken
      ) {
        expireStoredSession()
      }

      return Promise.reject(error)
    }

    originalRequest._retry = true

    const refreshToken = getStoredRefreshToken()

    if (!refreshToken) {
      expireStoredSession()
      return Promise.reject(error)
    }

    originalRequest._refreshToken = refreshToken

    try {
      const accessToken = await refreshAccessTokenSingleFlight(refreshToken)

      if (getStoredRefreshToken() !== refreshToken) {
        return Promise.reject(createStaleSessionRequestError(originalRequest))
      }

      originalRequest.headers.Authorization = `Bearer ${accessToken}`
      return apiClient(originalRequest)
    } catch (refreshError) {
      return Promise.reject(refreshError)
    }
  },
)

export default apiClient
