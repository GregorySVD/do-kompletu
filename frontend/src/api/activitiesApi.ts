import type {
  Activity,
  ActivityCategory,
  ActivityDetails,
  CreateActivityPayload,
} from '../types/activity'
import apiClient from './apiClient'

export async function getActivities(): Promise<Activity[]> {
  const response = await apiClient.get<Activity[]>('/api/v1/activities', {
    // Temporary MVP limit: local filtering needs the complete current dataset.
    params: { limit: 100, offset: 0 },
  })

  return response.data
}

export async function getActivityCategories(): Promise<ActivityCategory[]> {
  const response = await apiClient.get<ActivityCategory[]>('/api/v1/categories')

  return response.data
}

export async function getActivityById(
  activityId: string,
): Promise<ActivityDetails> {
  const response = await apiClient.get<ActivityDetails>(
    `/api/v1/activities/${activityId}`,
  )

  return response.data
}

export async function createActivity(
  payload: CreateActivityPayload,
): Promise<ActivityDetails> {
  const response = await apiClient.post<ActivityDetails>(
    '/api/v1/activities',
    payload,
  )

  return response.data
}
