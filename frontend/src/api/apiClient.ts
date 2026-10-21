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
}

const authEndpointsWithoutRefresh = new Set([
  '/api/v1/auth/login',
  '/api/v1/auth/register',
  '/api/v1/auth/refresh',
  '/api/v1/auth/token',
])

let pendingAccessTokenRefresh: Promise<string> | null = null

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

apiClient.interceptors.request.use((config) => {
  const accessToken = getStoredAccessToken()

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }

  return config
})

function isAuthEndpointWithoutRefresh(url: string | undefined) {
  if (!url) {
    return false
  }

  const pathname = new URL(url, 'http://localhost').pathname.replace(/\/$/, '')
  return authEndpointsWithoutRefresh.has(pathname)
}

function refreshAccessTokenSingleFlight(refreshToken: string) {
  pendingAccessTokenRefresh ??= requestAccessTokenRefresh(refreshToken)
    .then(({ access_token: accessToken }) => {
      storeAccessToken(accessToken)
      return accessToken
    })
    .catch((error: unknown) => {
      if (
        axios.isAxiosError(error) &&
        (error.response?.status === 401 || error.response?.status === 422)
      ) {
        expireStoredSession()
      }

      throw error
    })
    .finally(() => {
      pendingAccessTokenRefresh = null
    })

  return pendingAccessTokenRefresh
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || error.response?.status !== 401) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as RetryableRequestConfig | undefined

    if (
      !originalRequest ||
      originalRequest._retry ||
      isAuthEndpointWithoutRefresh(originalRequest.url)
    ) {
      return Promise.reject(error)
    }

    originalRequest._retry = true

    const refreshToken = getStoredRefreshToken()

    if (!refreshToken) {
      expireStoredSession()
      return Promise.reject(error)
    }

    try {
      const accessToken = await refreshAccessTokenSingleFlight(refreshToken)
      originalRequest.headers.Authorization = `Bearer ${accessToken}`
      return apiClient(originalRequest)
    } catch (refreshError) {
      return Promise.reject(refreshError)
    }
  },
)

export default apiClient
