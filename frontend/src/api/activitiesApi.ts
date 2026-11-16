import type {
  Activity,
  ActivityCategory,
  ActivityDetails,
  ActivityPhoto,
  CheckInActivityPayload,
  CreateActivityPayload,
  UpdateActivityPayload,
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

export async function getActivityPhotos(
  activityId: string,
): Promise<ActivityPhoto[]> {
  const response = await apiClient.get<ActivityPhoto[]>(
    `/api/v1/activities/${activityId}/photos`,
  )

  return response.data
}

export async function uploadActivityPhoto(
  activityId: string,
  file: File,
): Promise<ActivityPhoto> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post<ActivityPhoto>(
    `/api/v1/activities/${activityId}/photos`,
    formData,
  )

  return response.data
}

export async function deleteActivityPhoto(
  activityId: string,
  photoId: string,
): Promise<void> {
  await apiClient.delete<void>(
    `/api/v1/activities/${activityId}/photos/${photoId}`,
  )
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

export async function updateActivity(
  activityId: string,
  payload: UpdateActivityPayload,
): Promise<ActivityDetails> {
  const response = await apiClient.patch<ActivityDetails>(
    `/api/v1/activities/${activityId}`,
    payload,
  )

  return response.data
}

export async function cancelActivity(
  activityId: string,
): Promise<ActivityDetails> {
  const response = await apiClient.post<ActivityDetails>(
    `/api/v1/activities/${activityId}/cancel`,
  )

  return response.data
}

export async function finalizeActivity(
  activityId: string,
): Promise<ActivityDetails> {
  const response = await apiClient.post<ActivityDetails>(
    `/api/v1/activities/${activityId}/finalize`,
  )

  return response.data
}

export async function joinActivity(
  activityId: string,
): Promise<ActivityDetails> {
  const response = await apiClient.post<ActivityDetails>(
    `/api/v1/activities/${activityId}/join`,
  )

  return response.data
}

export async function leaveActivity(
  activityId: string,
): Promise<ActivityDetails> {
  const response = await apiClient.delete<ActivityDetails>(
    `/api/v1/activities/${activityId}/join`,
  )

  return response.data
}

export async function confirmActivity(
  activityId: string,
): Promise<ActivityDetails> {
  const response = await apiClient.post<ActivityDetails>(
    `/api/v1/activities/${activityId}/confirm`,
  )

  return response.data
}

export async function checkInActivity(
  activityId: string,
  payload: CheckInActivityPayload,
): Promise<ActivityDetails> {
  const response = await apiClient.post<ActivityDetails>(
    `/api/v1/activities/${activityId}/check-in`,
    payload,
  )

  return response.data
}
