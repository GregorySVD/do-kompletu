import apiClient from './apiClient'
import type {
  LoginFormValues,
  RegisterFormValues,
  TokenPair,
  UpdateUserProfilePayload,
  UserProfile,
} from '../types/auth'
export { requestAccessTokenRefresh as refreshAccessToken } from './authRefreshApi'

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

export async function getCurrentUser(): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>('/api/v1/users/me')

  return response.data
}

export async function updateCurrentUser(
  payload: UpdateUserProfilePayload,
): Promise<UserProfile> {
  const response = await apiClient.patch<UserProfile>(
    '/api/v1/users/me',
    payload,
  )

  return response.data
}
