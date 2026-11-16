import type {
  AdminActivity,
  AdminPaginationParams,
  AdminUser,
  SetAdminUserActivePayload,
} from '../types/admin'
import apiClient from './apiClient'

export async function getAdminUsers(
  params: AdminPaginationParams,
  signal?: AbortSignal,
): Promise<AdminUser[]> {
  const response = await apiClient.get<AdminUser[]>('/api/v1/admin/users', {
    params,
    signal,
  })

  return response.data
}

export async function setAdminUserActive(
  userId: string,
  payload: SetAdminUserActivePayload,
): Promise<AdminUser> {
  const response = await apiClient.patch<AdminUser>(
    `/api/v1/admin/users/${userId}/active`,
    payload,
  )

  return response.data
}

export async function getAdminActivities(
  params: AdminPaginationParams,
  signal?: AbortSignal,
): Promise<AdminActivity[]> {
  const response = await apiClient.get<AdminActivity[]>(
    '/api/v1/admin/activities',
    { params, signal },
  )

  return response.data
}

export async function cancelAdminActivity(
  activityId: string,
): Promise<AdminActivity> {
  const response = await apiClient.post<AdminActivity>(
    `/api/v1/admin/activities/${activityId}/cancel`,
  )

  return response.data
}
