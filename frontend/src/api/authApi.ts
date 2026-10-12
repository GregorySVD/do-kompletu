import apiClient from './apiClient'
import type {
  AccessTokenResponse,
  LoginFormValues,
  RegisterFormValues,
  TokenPair,
  UserProfile,
} from '../types/auth'

type RegisterPayload = Omit<RegisterFormValues, 'confirm_password'>

export async function registerUser(
  payload: RegisterPayload,
): Promise<UserProfile> {
  const response = await apiClient.post<UserProfile>(
    '/api/v1/auth/register',
    payload,
  )

  return response.data
}

export async function loginUser(payload: LoginFormValues): Promise<TokenPair> {
  const response = await apiClient.post<TokenPair>(
    '/api/v1/auth/login',
    payload,
  )

  return response.data
}

export async function refreshAccessToken(
  refreshToken: string,
): Promise<AccessTokenResponse> {
  const response = await apiClient.post<AccessTokenResponse>(
    '/api/v1/auth/refresh',
    { refresh_token: refreshToken },
  )

  return response.data
}

export async function getCurrentUser(): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>('/api/v1/users/me')

  return response.data
}
