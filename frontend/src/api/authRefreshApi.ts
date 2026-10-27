import axios from 'axios'
import type { AccessTokenResponse } from '../types/auth'

const authRefreshClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

export async function requestAccessTokenRefresh(
  refreshToken: string,
): Promise<AccessTokenResponse> {
  const response = await authRefreshClient.post<AccessTokenResponse>(
    '/api/v1/auth/refresh',
    { refresh_token: refreshToken },
  )

  return response.data
}
