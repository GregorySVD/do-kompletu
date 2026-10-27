import { useQuery } from '@tanstack/react-query'
import { getActivityById } from '../../api/activitiesApi'
import { useAuth } from '../../context/auth'

export function getActivityDetailsQueryKey(
  activityId: string,
  userId?: string,
) {
  return ['activity-details', userId ?? 'anonymous', activityId] as const
}

export function useActivityDetailsQuery(activityId: string) {
  const { isLoading, user } = useAuth()

  return useQuery({
    queryKey: getActivityDetailsQueryKey(activityId, user?.id),
    queryFn: () => getActivityById(activityId),
    enabled: activityId !== '' && !isLoading,
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: true,
  })
}
