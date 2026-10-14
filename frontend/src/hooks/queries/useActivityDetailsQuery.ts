import { useQuery } from '@tanstack/react-query'
import { getActivityById } from '../../api/activitiesApi'
import { activitiesQueryKey } from './useActivitiesQuery'

export function useActivityDetailsQuery(activityId: string) {
  return useQuery({
    queryKey: [...activitiesQueryKey, activityId],
    queryFn: () => getActivityById(activityId),
    enabled: activityId !== '',
    staleTime: 60_000,
    retry: false,
  })
}
