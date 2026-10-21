import { useQuery } from '@tanstack/react-query'
import { getActivityById } from '../../api/activitiesApi'
import { activitiesQueryKey } from './useActivitiesQuery'

export function getActivityDetailsQueryKey(activityId: string) {
  return [...activitiesQueryKey, activityId] as const
}

export function useActivityDetailsQuery(activityId: string) {
  return useQuery({
    queryKey: getActivityDetailsQueryKey(activityId),
    queryFn: () => getActivityById(activityId),
    enabled: activityId !== '',
    staleTime: 60_000,
    retry: false,
  })
}
