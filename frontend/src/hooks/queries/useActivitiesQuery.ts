import { useQuery } from '@tanstack/react-query'
import { getActivities } from '../../api/activitiesApi'

export const activitiesQueryKey = ['activities'] as const

export function useActivitiesQuery() {
  return useQuery({
    queryKey: activitiesQueryKey,
    queryFn: getActivities,
    staleTime: 60_000,
    retry: 1,
  })
}
