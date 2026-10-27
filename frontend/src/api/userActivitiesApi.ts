import type { ActivityDetails } from '../types/activity'
import apiClient from './apiClient'

export type ActivityRelation = 'joined' | 'organized' | 'waitlisted'
export type ActivityScope = 'upcoming' | 'history'

interface GetMyActivitiesParams {
  relation: ActivityRelation
  scope?: ActivityScope
  limit: number
  offset: number
}

export async function getMyActivities({
  relation,
  scope,
  limit,
  offset,
}: GetMyActivitiesParams): Promise<ActivityDetails[]> {
  const params: GetMyActivitiesParams = {
    relation,
    limit,
    offset,
  }

  if (scope !== undefined) {
    params.scope = scope
  }

  const response = await apiClient.get<ActivityDetails[]>(
    '/api/v1/users/me/activities',
    { params },
  )

  return response.data
}
